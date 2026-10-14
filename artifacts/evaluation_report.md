# Evaluation Report

## Goal
Predict total interactions using six post attributes.

## Evaluation method
- Training posts: 399
- Test posts: 100
- Random split with random_state=42.
- Five-fold cross-validation within the training set.
- Selection by lowest mean cross-validation MAE.
- MAE is measured in interactions; lower is better.
- The test set was inspected during development, so it is
  not a completely untouched final evaluation.

## Cross-validation results
| Model | CV MAE | CV standard deviation |
|---|---:|---:|
| CatBoost depth 4 | 146.55 | 56.94 |
| CatBoost depth 3 | 146.70 | 56.49 |
| Baseline | 152.44 | 59.86 |

## Selected model
CatBoost depth 4

## Test results
- Baseline MAE: 120.45
- Selected model MAE: 125.54
- Model minus baseline MAE: 5.09

## Conclusion
The selected model did not outperform the baseline on this test split. Predictive value is not established.

## Interpretation
Variation across folds is substantial.
The small difference between the CatBoost variants does
not establish a meaningful advantage for either variant.
This random split does not measure performance on future
periods or on different accounts.
