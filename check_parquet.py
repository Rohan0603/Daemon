import pandas as pd
df = pd.read_parquet('fine_tuning/soup/batch_00000.parquet')
print(f'Shape: {df.shape}')
print(f'Columns: {df.columns.tolist()}')
print(f'\nFirst 3 rows:')
print(df.head(3).to_string())
print(f'\nDtypes:')
print(df.dtypes)