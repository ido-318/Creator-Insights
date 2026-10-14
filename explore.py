import pandas as pd

df = pd.read_csv("data/dataset_Facebook.csv", sep=";")

print("Rows and columns:", df.shape)
print("\nFirst 5 rows:")
print(df.head())

print("\nMissing values per column:")
print(df.isna().sum())


# Candidate inputs known before publication
input_columns = [
    "Type",
    "Category",
    "Post Month",
    "Post Weekday",
    "Post Hour",
    "Paid",
]

print("\nInput column types:")
print(df[input_columns].dtypes)

print("\nValues and counts:")
for column in input_columns:
    print(f"\n--- {column} ---")
    print(df[column].value_counts(dropna=False).sort_index())

print("\nTarget summary:")
print(df["Total Interactions"].describe())


print("\nTop 5 posts by total interactions:")
columns_to_show = [
    "Type",
    "Paid",
    "comment",
    "like",
    "share",
    "Total Interactions",
]

top_posts = df.nlargest(5, "Total Interactions")
print(top_posts[columns_to_show].to_string(index=False))

print("\nPost with missing Paid:")
print(
    df.loc[df["Paid"].isna(), columns_to_show]
    .to_string(index=False)
)

# Check the total only where all three components are present
components = ["comment", "like", "share"]
complete_rows = df[components].notna().all(axis=1)
checked = df.loc[complete_rows]

calculated_total = checked[components].sum(axis=1)
mismatches = calculated_total != checked["Total Interactions"]

print("\nRows checked:", len(checked))
print("Interaction total mismatches:", mismatches.sum())