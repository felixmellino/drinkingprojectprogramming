"""Player help displayed from the Profile menu."""

import streamlit as st

from core.constants import MAX_GPS_ACCURACY_M
from core.scoring_v1 import DRINK_LABELS, SIZE_LABELS, new_rules

STANDARD_RULES = new_rules()
POINTS = STANDARD_RULES["points"]
POINTS_TABLE = "\n".join([
    "| Drink | Small | Medium | Large |",
    "| --- | ---: | ---: | ---: |",
    *[
        "| " + " | ".join([DRINK_LABELS[drink], *(str(POINTS[drink][size]) for size in SIZE_LABELS)]) + " |"
        for drink in ("beer", "wine", "mixed")
    ],
])

FAQ = (
    ("Lobbies and teams", (
        ("How do I join a lobby?",
         "Open **Profile → Lobbies → Join with a code**, enter the invite code, then tap **Join lobby**."),
        ("How do I create a lobby and invite friends?",
         "Go to **Profile → Lobbies → Create a lobby**. Pick a name, Individual or Team mode, "
         "a duration, and a timezone. Tap **Create lobby**, then share the invite code from the lobby details."),
        ("How do I switch lobbies?",
         "Go to **Profile → Lobbies** and tap **View lobby** on the one you want to play in. "
         "Your selection controls what you see in **Map**, **Ranks**, **Check in**, **Games**, and **Photos**."),
        ("How do I join a team?",
         "Tap **Join team** on a team with space, or get assigned automatically if the lobby uses random assignment. "
         "Your team locks after your first scored check-in. Team totals determine rank and territory ownership."),
        ("What happens when my lobby’s season ends?",
         "Open it under **Past Lobbies** to see the final standings. Each lobby runs one competition. "
         "Create a new lobby to start a competition with fresh scores."),
    )),
    ("Check-ins and points", (
        ("How do I score points?",
         "Open your lobby and tap **+** at the bottom. Take a photo of your drink in the app, "
         "choose its type and size, then tap **Submit** once your location is verified. "
         "**Check in** previews your points before you submit."),
        ("When can I check in?",
         "During an active season, standard scoring runs continuously from **Thursday at 18:00** until "
         "**Sunday at 18:00**, in the lobby’s timezone. Test lobbies open on **Wednesday at 08:00** "
         "and close at the same Sunday cutoff."),
        ("How many points is my drink worth?",
         f"These are the base points for a new lobby. **Check in** shows your points with any active boost.\n\n"
         f"{POINTS_TABLE}\n\nA **shot** is worth **{POINTS['shot']['standard']} points** and has one serving size."),
        ("Why can’t I check in again yet?",
         f"Wait **{STANDARD_RULES['cooldown_seconds'] // 60} minutes** after your last successful check-in "
         "in the same lobby. **Check in** shows how much time is left."),
        ("What if the app can’t verify my location?",
         "Turn on **Location** in **Profile** and allow location access in your browser. If the reading is "
         f"too inaccurate, step outside or closer to a window and wait for it to update. The app needs a fresh "
         f"reading accurate to within **{MAX_GPS_ACCURACY_M:g} metres**."),
        ("Can I score outside a territory?",
         "Yes. A check-in with a verified location outside all marked areas earns **season points only**. "
         "Inside a territory, your check-in also earns points for that area."),
        ("Can I fix a check-in if I picked the wrong drink or size?",
         "Open your entry in **Photos** and choose **Correct drink or size** within "
         f"**{STANDARD_RULES['correction_seconds'] // 60} minutes** of submitting, while the season is still active. "
         "The app recalculates the scores after you save."),
    )),
    ("Map and rankings", (
        ("How do I claim a territory?",
         "Check in inside an area marked on **Map**. The player or team with the most territory points "
         "in that area owns it. Tap a territory to see who owns it and how many points you need to take it."),
        ("What do I get for owning a territory?",
         "When a rival checks in there, the current owner earns an extra "
         f"**{STANDARD_RULES['owner_bonus_quarters_per_point'] * 25}%** of the drink’s eligible points as season points. "
         "The rival keeps their points. In team lobbies, the bonus goes to the owning team."),
        ("Where can I see who’s winning?",
         "Open **Ranks** for the selected lobby’s season leaderboard. The highest season total wins. "
         "If players or teams tie, whoever reached that score first ranks higher. "
         "Open **Map** to see who leads in each territory."),
    )),
    ("Games and photos", (
        ("How do I play a minigame?",
         "Open **Games**, choose a duel, and challenge another player in your lobby. If someone challenges you, "
         "open that game to accept or decline. In team lobbies, you can challenge players on rival teams."),
        ("What can I win in a duel?",
         "- **Chug Duel** awards the winner both drinks’ base season points.\n"
         "- **Reaction Duel** is a best-of-three reaction challenge. The winner takes the agreed stake of "
         "**1–10 season points** from the other player.\n"
         "- **Quiz Duel** rewards fast, correct answers. The winner takes the agreed stake of "
         "**3–10 season points** from the other player.\n"
         "- **Time Duel** rewards the closest timing with **1.25× season points** on ordinary check-ins for one hour."),
        ("Who can see my check-in photos?",
         "You can see your own in **Photos**, and teammates can see their team’s photos. Other lobby members can "
         "see yours if you enable sharing under **Profile → Account & security → Photo privacy**. In team lobbies, "
         "sharing with the rest of the lobby also requires every current teammate to turn sharing on. "
         "You can delete your own photo from its details and keep the points you earned."),
    )),
)


@st.dialog("FAQ / Help")
def show_faq():
    for section, questions in FAQ:
        st.subheader(section, anchor=False)
        for question, answer in questions:
            with st.expander(question):
                st.markdown(answer)
    if st.button("Close", key="close_faq", width="stretch"):
        st.rerun()
