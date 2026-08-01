These are the only names the descriptor understands. Anything else is skipped.

STATE_SHELL_MENU = Main menu
STATE_AVENGER = On board the Avenger
STATE_GEOSCAPE = Geoscape
STATE_SQUADSELECT = Squad select
STATE_MISSION_EXPLORE = In a mission, concealed / calm
STATE_MISSION_COMBAT = In a mission, fighting
STATE_VICTORY = Mission won
STATE_DEFEAT = Mission lost
STATE_RESISTANCE_RADIO = Radio Mode's station pool

Each of the first six also has a _LOOP variant — STATE_AVENGER_LOOP and
so on, this is when you want it to pick a random track from the folder and loop it.

If it's not in a _LOOP folder the game will just cycle through tracks

STATE_RESISTANCE_RADIO is the interesting one: it feeds Radio Mode,
where every track starts at a random point as though you'd tuned into a
broadcast already in progress. Long-form content — DJ banter, fake adverts,
hour-long station rips — is exactly what it's for.