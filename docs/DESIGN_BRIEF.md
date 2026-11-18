# Design brief: WeGoPub design system

## Your task
Create a complete, modern **design system** and key screens for **WeGoPub**, a
mobile-first social drinking game.

**I want several design ideas, not one.** Give me **at least 4 clearly
different design directions**. For each direction:
1. A name and a one-line mood ("dark night game", "loud social club", …).
2. Colour tokens (light and/or dark), typography scale, spacing, radius, shadows.
3. Component styles (list below).
4. The 5 key screens: **Map, Check-in, Leaderboard, Lobby, Profile**.
5. Short pros and cons.

Finish with a side-by-side comparison and a recommendation.

---

## The product in one paragraph
WeGoPub is a social game for groups of friends (students in Lisbon). Players
join a **lobby** with an invite code. During a **season**, every drink you have
counts: you take a **fresh photo**, pick the drink and its size, and the app
checks your **phone location automatically**. The drink earns **points**, and if
you're inside one of the **territories** on the city map (24 areas in central
Lisbon plus the Nova SBE campus), those points also count for that territory.
Whoever has the most points in a territory **owns** it, and owners earn a 25%
bonus when others drink there. The player with the most points wins the season.

## Audience and tone
- 19–26-year-old students, nightlife, groups of friends, competitive banter.
- Used **at night, in bars, on a phone, one-handed**, often in a hurry.
- Tone: **playful, social, competitive, a bit cheeky, never childish.**

## Reference: a modern social app
Design it like a **modern social app**, not an admin tool. Take cues from:
- **BeReal / Instagram:** photo-first, big images, avatars, quick actions.
- **Strava:** stats, leaderboards, progress, achievements, clean numbers.
- **Pokémon GO / Ingress:** the map *is* the game; territories you capture,
  floating HUD and cards over a full-screen map.
- **Untappd:** drink check-ins as social moments.

Principles: thumb-friendly bottom navigation, one clear primary action per
screen, big touch targets (≥ 44 px), bold numbers, avatars everywhere,
delightful but quick feedback (success moments when you score or capture).

---

## Fixed constraints (must hold in every direction)
- **Territory colours are fixed:** **green = yours**, **red = someone else's**,
  **grey = unclaimed**. Keep them in every direction (shades may adapt).
  → The **brand accent must not be red or green**, so buttons are never
  confused with territory status.
- Error / warning / success messages must stay distinguishable from the
  territory colours (for example icon + text, not colour alone).
- **Mobile first** (390 × 844 px), must also work on desktop.
- **Accessible:** WCAG AA contrast, readable in a dark bar and in sunlight.
- **Icons:** one consistent line icon set (Material Symbols Rounded). No emojis
  as UI icons.
- **Implementation:** the app is built with **Streamlit (Python)** and styled
  with CSS on top of standard widgets (buttons, radios, segmented controls,
  expanders, tables, camera). The map is a **deck.gl map with a Carto base map**
  (light, voyager or dark style). Designs should be achievable with CSS: no
  complex gestures, swipes or native-only components.

---

## Colour schemes to explore (from my references)
Use at least **one** direction per scheme below where it makes sense, and feel
free to propose your own. Keep the territory colours above in all of them.

| Scheme | Colours | Note |
|---|---|---|
| **HYRO, dark** | Charcoal `#121212`, Warm white `#FDF9EA`, Performance orange `#FE5105` | Sporty and energetic; orange is distinct from red/green. My current favourite. |
| **HYRO, light** | Warm white `#FDF9EA` background, Charcoal `#121212` text, Orange `#FE5105` accent | Same palette, daylight version. |
| **Base Club** | Raspberry pink `#CC1466`, Mellow white `#FEFDFE`, Pastel turquoise/mint `#63F5C3` | Loud, playful, social-club feel. Mint competes with "yours" green: solve that. |
| **Rush** | Midnight navy `#1A2841`, Old cream `#F0E1CE`, Vintage red `#B11722` | Retro, characterful. Red clashes with "someone else's" red: use it sparingly or adapt. |
| **Tennis** | Sky blue `#2C99D6`, Cloud white `#F8FAFC`, Scarlet red `#EB2F33` | Fresh, sporty. Scarlet must not be used for actions. |
| **Moon** | `#212A31`, `#2E3944`, teal `#124E66`, `#748D92`, `#D3D9D4` | Calm, premium, editorial. |

---

## All features and screens

### Navigation
- Bottom navigation bar with 6 destinations: **Profile, Lobby, Check in (big
  central + button), Map, Leaderboard, Photo history**. Active tab highlighted.

### First opening and account
- Create account: first name, surname, public username, email, password +
  confirmation (minimum 8 characters). Only the username is public.
- Log in with email + password; "Remember me on this device" (30 days).
- After login the browser asks for **location permission** once.
- States: wrong password, too many attempts (wait), service unavailable.

### Profile
- Profile header with **profile picture** (or initials), username, name.
- Menu with separate views and "Back to Profile":
  - **Edit profile:** username, first name, surname (email read-only);
    profile picture: **Upload photo / Take photo**, circular crop preview,
    Save, Replace, Remove (falls back to initials).
  - **Friends:** search usernames (partial, case-insensitive), send request,
    incoming requests (Accept / Decline), outgoing (Cancel), friends list
    (private), Remove friend; after a decline a 10-minute wait.
  - **My stats:** points, rank and territories owned in the current lobby.
  - **Account & security:** change password (needs current password; signs
    out all devices).
  - **Log out.**

### Lobby
- List of **your lobbies only**:
  - **Active lobbies** (highlighted): name, current leader (avatar + username),
    countdown to the end and exact end time; button **Open lobby**.
  - **Past lobbies** (muted): name, winner, end time; **View results**.
  - "No Leader" when nobody has scored yet.
- **Create lobby:** name, duration (**1 week / 1 month / 3 months**),
  timezone, optional **Test season** checkbox (opens Wednesday instead of
  Thursday, clearly labelled everywhere).
- **Join lobby** with a 6-character invite code; show/share the code.
- Retry state if lobby setup failed.

### Check in (central + button), the core action
1. **Camera opens immediately** (rear camera), one big shutter button;
   **Retake**; blocked/unavailable camera with a clear message and Retry.
2. Photo shown in a rounded frame.
3. **Drink:** Beer, Wine, Shot, Mixed drink. **Size:** Small / Medium / Large
   (beer 250/330/500 ml, wine 100/150/250 ml; shot has no size).
4. **Live points preview:** "+3 season points, +3 territory points if you're in
   a territory". Points table: beer 1/2/3, wine 1/2/4, mixed 2/3/5, shot 4.
5. **Location card** (automatic, no button), states:
   finding you… · found, accurate to ±12 m · not precise enough (> 50 m) ·
   blocked (how to allow it) · outside all territories (season points only) ·
   reading too old (refreshing).
6. **Detected territory:** name, current owner (avatar), "you need 3 more points
   to take it" / "you own it" / "unclaimed: your drink claims it", and the
   owner's 25% bonus note.
7. **Submit** (full width). Disabled reasons shown clearly.
8. Before the form: **scoring closed** ("Opens Thu 19 Nov at 18:00"),
   **cooldown** ("Wait 1:24 before your next check-in"), season ended.
9. **Success moment:** "+3 points", "You captured Shortys!", owner bonus info.
10. Errors: couldn't save (retry), location not accurate, duplicate.

### Map (the game screen)
- Full-screen map, territories coloured **green / red / grey**, names on areas.
- **Your position**: blue dot with accuracy circle.
- **Floating HUD** at the top: lobby name, "2 / 24 yours · 19 free".
- **Quick-zoom chips:** Me, Bairro Alto, Lisbon, Nova SBE, All.
- Tap or hover an area: name, owner, your points there, points needed to take it.
- **Floating bottom card:** "You are in Shortys · owned by rival · you need
  3 more points" + big **Check in here** button.
- Legend, and a collapsible "All territories" list.

### Leaderboard
- **Personal summary:** your rank, season points (quarter points possible, for
  example 12.25), territories owned.
- **Season leaderboard:** top-3 medals, avatars/initials, YOU marker on your row.
- **Territory cards:** each territory with owner, every player's points as
  bars, unclaimed state.
- Refresh, loading and "unavailable" states (never fake zeros).

### Photo history (Memories)
- Lobby gallery, newest first, 4 per page: photo, username + avatar, territory,
  drink and size, points, time.
- **Details view:** correct drink/size within 2 minutes; **delete photo** (points
  stay); photos expire 30 days after the season.

### Minigame (planned, design a concept)
- One minigame per player per game night (for example a reaction test or
  virtual beer pong). It gives **special items** (for example a points
  multiplier), not points. Show: start screen, "already played tonight",
  result with the item won, and an inventory of items.

### General states to design
Empty states (no lobby yet, no drinks yet, no friends), loading skeletons,
offline/service errors, permission prompts (camera, location), toasts.

---

## Components to define in every direction
Primary / secondary / ghost / destructive buttons · icon buttons · bottom nav
with central action · segmented controls and chips · cards (stat card, list
card, photo card, territory card, floating HUD/card over the map) · list rows
with avatar, rank badge and YOU marker · avatars with initials fallback ·
status pills (yours / theirs / free, test season, closed) · inputs, password
field, checkbox, select · alerts (info, success, warning, error) and toasts ·
countdown/timer · progress bars · camera frame with shutter · map legend.

## Deliverable format
For each direction, give the tokens as code I can paste:

```css
:root {
  /* colours */
  --bg: ; --surface: ; --surface-raised: ; --text: ; --text-muted: ;
  --accent: ; --on-accent: ; --border: ;
  --territory-yours: ; --territory-theirs: ; --territory-free: ;
  --success: ; --warning: ; --error: ; --info: ;
  /* type */
  --font-display: ; --font-body: ; --text-xs … --text-3xl: ;
  /* shape */
  --radius-sm: ; --radius-md: ; --radius-lg: ; --radius-pill: ;
  --space-1 … --space-8: ; --shadow-card: ; --shadow-float: ;
}
```

…plus a matching Streamlit theme:

```toml
[theme]
base = "dark"            # or "light"
primaryColor = ""
backgroundColor = ""
secondaryBackgroundColor = ""
textColor = ""
font = ""
```
