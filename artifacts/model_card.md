# Model Card

## Model
CatBoost depth 4

## Intended use
Educational demonstration of a validated AI/data workflow.
Estimate total Facebook post interactions.

## Training data
UCI Facebook Metrics: historical posts from one cosmetics
brand's Facebook page.
The cleaned dataset has 499 rows.
One row with missing paid status was excluded.
The saved model was fitted on 399 training rows.

## Inputs
post_type, category, post_month, post_weekday, post_hour, paid

Month and hour are represented as numbers without explicit
cyclic encoding. Category codes retain their source meaning.
The paid flag is assumed to be known when making a prediction.

## Target
total_interactions, measured as an interaction count.
This is not an engagement rate.

## Performance
- Test MAE: 125.54
- Baseline test MAE: 120.45

The selected model did not outperform the baseline on this test split. Predictive value is not established.

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
Input schema version: 1.0.
See cv_results.csv, data_split.csv and test_predictions.csv.
