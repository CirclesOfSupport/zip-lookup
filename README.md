# zip-lookup
State &amp; VAMC lookup from zip code for Early Alert

## How the lookups work

`POST /` with `{"zipcode": "..."}` returns `state`, `vamc_presumed` and `zip_prefix`.

- **State needs a complete, real five-digit zip.** `src/state_lookup.py` maps every zip in the GeoNames
  postal-code files (the US file plus Puerto Rico, the Virgin Islands, Guam, American Samoa and the Northern
  Marianas) to its state. A complete zip in a military-only prefix (090-099, 340, 962-966) is AE, AA or AP.
  Anything else - a zip that lost its leading zero (`2809` for `02809`), a short or unknown zip - comes back
  with an empty state. We used to fall back to the first three digits, which turned `2809` into North
  Carolina; an empty state is visible and fixable, a wrong one is not.
- **VAMC still uses the three-digit prefix**, because the VA catchment data only exists at that grain.
- Zips like `30310.0` and `12345-6789` are read as their first five digits.

To rebuild the state table from GeoNames: `python tools/generate_state_lookup.py`.

Tests: `pip install flask pytest && python -m pytest tests`.
