
#!/usr/bin/env python3
import pathlib, importlib, sys
root = pathlib.Path(__file__).resolve().parents[1]
csv = root/'gold'/'dai_v1.csv'
parq = root/'gold'/'dai_v1.parquet'
try:
    pa = importlib.import_module('pyarrow')
    pq = importlib.import_module('pyarrow.parquet')
    import pandas as pd
    df = pd.read_csv(csv)
    tbl = pa.Table.from_pandas(df)
    pq.write_table(tbl, parq, compression='zstd')
    print('wrote', parq)
except Exception as e:
    try:
        import pandas as pd
        df = pd.read_csv(csv)
        df.to_parquet(parq, index=False)
        print('wrote', parq)
    except Exception as e2:
        print('ERROR: need pyarrow or pandas to write Parquet:', e, e2, file=sys.stderr)
        sys.exit(2)
