# Shift11 sequence-validation patch

## Files
- `src/validation.py`: reusable validator and command-line JSON check.
- `tests/test_generator.py`: replacement test suite, including sequence-level checks.

## Install
Copy `src/validation.py` to the existing `Shift11/src/` directory. Replace `Shift11/tests/test_generator.py` with the supplied file. Do not overwrite your existing `src/generator.py` or `src/models.py`.

## Run
From the project root:

```powershell
python -m src.validation data/match_001.json
python -m unittest discover -s tests -v
```

The validator checks structural validity and some event-sequence invariants. It does not prove that the synthetic match is fully realistic or that a momentum shift occurred. Review any reported sequence issue before weakening a rule; if a rule exposes a generator bug, correct the generator instead.
