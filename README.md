# mm2-trade-checker
mm2 trade checker. uses value, stability, demand, rarity, etc to determine if a trade if w/f/l.
put all the values in a folder called "data_txt" (data_txt.txt)
MM2 trade checker that uses value, stability, demand, rarity, etc. to determine if a trade is W/F/L.

## Data sources
The checker can load data from:
- A `data_txt` folder containing `.txt` files (default behavior).
- Individual `mm2values_*.txt` files in the repo root if `data_txt` is missing.
- Custom paths via `--data-path` (files or folders, can be used multiple times).

Examples:
```bash
python trade_ai.py --data-path data_txt
python trade_ai.py --data-path mm2values_godly.txt --data-path mm2values_ancient.txt
```

## Helpful options
- `--list` to show all loaded item names.

Example:
```bash
python trade_ai.py --list
```
