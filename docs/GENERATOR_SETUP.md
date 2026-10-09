Shift11 Generator Setup
=======================

1. Extract this ZIP into your existing Shift11 project folder, preserving folders.
   The new file should be Shift11/src/generator.py and the tests should be in
   Shift11/tests/test_generator.py.
2. Do not replace src/models.py with a file from this ZIP. The generator expects
   your updated models.py, including Match.attacking_direction(), period,
   possession_team_id, receiver_player_id, and duration_seconds.
3. From the Shift11 project root, run:

   python -m src.generator --seed 42 --scenario balanced

   This should create data/match_001.json.
4. Run automated checks from the same project root:

   python -m unittest discover -s tests -v

Scenarios available: balanced, high_pressing, counterattack,
defensive_dominance, harmless_possession.

The generated events are synthetic. The scenario affects event-pattern
probabilities, but it does not automatically declare a momentum shift.
