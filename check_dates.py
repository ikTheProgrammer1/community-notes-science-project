
import csv
import sys
from datetime import datetime

min_ts = float('inf')
max_ts = float('-inf')

try:
    with open('data/notes-00000.tsv', 'r', encoding='utf-8') as f:
        reader = csv.reader(f, delimiter='\t')
        header = next(reader)
        try:
            idx = header.index('createdAtMillis')
        except ValueError:
            print('createdAtMillis column not found')
            sys.exit(1)
            
        for row in reader:
            if len(row) > idx:
                try:
                    ts = int(row[idx])
                    if ts < min_ts: min_ts = ts
                    if ts > max_ts: max_ts = ts
                except ValueError:
                    continue

    if min_ts != float('inf'):
        print(f'Start Date: {datetime.fromtimestamp(min_ts/1000).strftime("%Y-%m-%d %H:%M:%S")}')
        print(f'End Date: {datetime.fromtimestamp(max_ts/1000).strftime("%Y-%m-%d %H:%M:%S")}')
    else:
        print('No valid timestamps found')
except FileNotFoundError:
    print("File not found")
