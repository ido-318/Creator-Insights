import joblib
from sklearn.model_selection import KFold, cross_val_score
from catboost import CatBoostRegressor
from sklearn.dummy import DummyRegressor
from sklearn.metrics import mean_absolute_error
import json
from pathlib import Path

import pandas as pd
from sklearn.model_selection import train_test_split

from validate_data import validate_data

artifacts = Path(__file__).resolve().parent / "artifacts"

# Read only the clean dataset and its contract
df = pd.read_csv(artifacts / "clean_data.csv")
contract = json.loads(
    (artifacts / "dataset_contract.json").read_text(
        encoding="utf-8"
    )
)

# Stop before modeling if validation fails
errors = validate_data(df, contract)

if errors:
    print("Training blocked:")
    for error in errors:
        print(f"- {error}")
    raise SystemExit(1)

# Get inputs and target from the contract
X = df[contract["features"]]
y = df[contract["target"]]

X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.2,
    random_state=42,
)

print("Validation passed.")
print("Training posts:", len(X_train))
print("Test posts:", len(X_test))
print("Input columns:", X.columns.tolist())
print("Target:", y.name)

# Baseline: predict the training-set median for every post
baseline = DummyRegressor(strategy="median")
baseline.fit(X_train, y_train)

baseline_predictions = baseline.predict(X_test)

baseline_mae = mean_absolute_error(
    y_test,
    baseline_predictions,
)

print("\nBaseline results:")
print(
    "Constant prediction:",
    round(float(baseline_predictions[0]), 1),
)
print("MAE:", round(baseline_mae, 2))

comparison = pd.DataFrame({
    "actual": y_test.to_numpy(),
    "predicted": baseline_predictions,
})

print("\nFirst 10 test predictions:")
print(comparison.head(10).to_string(index=False))
# CatBoost receives the original columns, without Ridge preprocessing
cat_features = [
    "post_type",
    "category",
    "post_weekday",
    "paid",
]

catboost_model = CatBoostRegressor(
    iterations=300,
    depth=4,
    learning_rate=0.05,
    loss_function="MAE",
    random_seed=42,
    verbose=False,
    allow_writing_files=False,
)

catboost_model.fit(
    X_train,
    y_train,
    cat_features=cat_features,
)

catboost_predictions = catboost_model.predict(X_test)

catboost_mae = mean_absolute_error(
    y_test,
    catboost_predictions,
)

print("\nAll model results:")
print("\nModel comparison:")
print(f"Baseline MAE: {baseline_mae:.2f}")
print(f"CatBoost MAE: {catboost_mae:.2f}")

# Compare models using only the training set
folds = KFold(
    n_splits=5,
    shuffle=True,
    random_state=42,
)

# Put categorical column definitions in the model itself
# so cross-validation copies retain them.
candidates = {
    "Baseline": DummyRegressor(strategy="median"),
    "CatBoost depth 3": CatBoostRegressor(
        iterations=300,
        depth=3,
        learning_rate=0.05,
        loss_function="MAE",
        cat_features=cat_features,
        random_seed=42,
        verbose=False,
        allow_writing_files=False,
        thread_count=2,
    ),
    "CatBoost depth 4": CatBoostRegressor(
        iterations=300,
        depth=4,
        learning_rate=0.05,
        loss_function="MAE",
        cat_features=cat_features,
        random_seed=42,
        verbose=False,
        allow_writing_files=False,
        thread_count=2,
    ),
}

results = []

for name, model in candidates.items():
    fold_errors = []

    for fold_number, (train_idx, valid_idx) in enumerate(
        folds.split(X_train),
        start=1,
    ):
        X_fold_train = X_train.iloc[train_idx]
        X_fold_valid = X_train.iloc[valid_idx]

        y_fold_train = y_train.iloc[train_idx]
        y_fold_valid = y_train.iloc[valid_idx]

        fresh_model = type(model)(**model.get_params())

        fresh_model.fit(X_fold_train, y_fold_train)
        predictions = fresh_model.predict(X_fold_valid)

        fold_mae = mean_absolute_error(
            y_fold_valid,
            predictions,
        )
        fold_errors.append(fold_mae)

        print(f"{name} | Fold {fold_number} | MAE: {fold_mae:.2f}")

    errors = pd.Series(fold_errors)

    results.append({
        "model": name,
        "cv_mae_mean": errors.mean(),
        "cv_mae_std": errors.std(ddof=0),
    })

cv_results = pd.DataFrame(results).sort_values("cv_mae_mean")

print("\nCross-validation on training data only:")
print(cv_results.round(2).to_string(index=False))

cv_results.to_csv(
    artifacts / "cv_results.csv",
    index=False,
)

# Select using training cross-validation, not test performance
selected_name = cv_results.iloc[0]["model"]
selected_model = candidates[selected_name]

# Train the selected model on all 399 training posts
selected_model.fit(X_train, y_train)

# Evaluate on the existing held-out test set
test_predictions = selected_model.predict(X_test)
selected_test_mae = mean_absolute_error(
    y_test,
    test_predictions,
)

# Save the model together with its input definitions
model_bundle = {
    "model": selected_model,
    "model_name": selected_name,
    "features": contract["features"],
    "target": contract["target"],
    "contract_version": contract["contract_version"],
}

joblib.dump(model_bundle, artifacts / "model.joblib")

# Save input features and identify their evaluation split
features = X.copy()
features.index.name = "row_id"
features.to_csv(artifacts / "features.csv")

split_labels = pd.Series("train", index=X.index, name="split")
split_labels.loc[X_test.index] = "test"
split_labels.index.name = "row_id"
split_labels.to_csv(artifacts / "data_split.csv")

# Keep actual values and predictions for inspection
test_results = pd.DataFrame({
    "actual": y_test,
    "predicted": test_predictions,
})
test_results.index.name = "row_id"
test_results.to_csv(artifacts / "test_predictions.csv")

print("\nSelected model:", selected_name)
print(f"Selected model test MAE: {selected_test_mae:.2f}")
print("Saved model.joblib, features.csv, data_split.csv")
print("Saved test_predictions.csv")

# Build a Markdown comparison table without extra dependencies
table_lines = [
    "| Model | CV MAE | CV standard deviation |",
    "|---|---:|---:|",
]

for _, row in cv_results.iterrows():
    table_lines.append(
        f"| {row['model']} "
        f"| {row['cv_mae_mean']:.2f} "
        f"| {row['cv_mae_std']:.2f} |"
    )

comparison_table = "\n".join(table_lines)

test_difference = selected_test_mae - baseline_mae

if test_difference < 0:
    conclusion = (
        "The selected model outperformed the baseline "
        "on this test split."
    )
elif test_difference > 0:
    conclusion = (
        "The selected model did not outperform the baseline "
        "on this test split. Predictive value is not established."
    )
else:
    conclusion = "The selected model matched the baseline."

evaluation_report = f"""# Evaluation Report

## Goal
Predict total interactions using six post attributes.

## Evaluation method
- Training posts: {len(X_train)}
- Test posts: {len(X_test)}
- Random split with random_state=42.
- Five-fold cross-validation within the training set.
- Selection by lowest mean cross-validation MAE.
- MAE is measured in interactions; lower is better.
- The test set was inspected during development, so it is
  not a completely untouched final evaluation.

## Cross-validation results
{comparison_table}

## Selected model
{selected_name}

## Test results
- Baseline MAE: {baseline_mae:.2f}
- Selected model MAE: {selected_test_mae:.2f}
- Model minus baseline MAE: {test_difference:.2f}

## Conclusion
{conclusion}

## Interpretation
Variation across folds is substantial.
The small difference between the CatBoost variants does
not establish a meaningful advantage for either variant.
This random split does not measure performance on future
periods or on different accounts.
"""

model_card = f"""# Model Card

## Model
{selected_name}

## Intended use
Educational demonstration of a validated AI/data workflow.
Estimate total Facebook post interactions.

## Training data
UCI Facebook Metrics: historical posts from one cosmetics
brand's Facebook page.
The cleaned dataset has {len(df)} rows.
One row with missing paid status was excluded.
The saved model was fitted on {len(X_train)} training rows.

## Inputs
{", ".join(contract["features"])}

Month and hour are represented as numbers without explicit
cyclic encoding. Category codes retain their source meaning.
The paid flag is assumed to be known when making a prediction.

## Target
{contract["target"]}, measured as an interaction count.
This is not an engagement rate.

## Performance
- Test MAE: {selected_test_mae:.2f}
- Baseline test MAE: {baseline_mae:.2f}

{conclusion}

## Limitations
- Small, historical dataset from a single page.
- Only seven video posts in the cleaned dataset.
- Imbalanced post types and highly variable outcomes.
- No analysis of the actual text, image or video content.
- No demonstrated generalization to Instagram or new creators.
- Predictions are estimates, not guaranteed outcomes.

## Ethical considerations
Do not present these results as guaranteed growth advice.
Do not interpret correlations as causal effects.
The model should not be used as the sole basis for spending
advertising budgets or evaluating a creator's quality.

## Reproducibility
Random seed: 42.
Input schema version: {contract["contract_version"]}.
See cv_results.csv, data_split.csv and test_predictions.csv.
"""

(artifacts / "evaluation_report.md").write_text(
    evaluation_report,
    encoding="utf-8",
)

(artifacts / "model_card.md").write_text(
    model_card,
    encoding="utf-8",
)

print("Saved evaluation_report.md and model_card.md")