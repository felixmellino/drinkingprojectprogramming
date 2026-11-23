# WeGoPub – Design brief

## What it is about
WeGoPub is a drinking game as a phone app for students in Lisbon (university project, Nova SBE).
Friends compete against each other in a **lobby** for one season (about a month). On game nights
(Thursday to Sunday) you log every drink with a **photo**, and your location assigns it to a **territory** on the map.
Whoever has the most points in a territory owns it. Whoever has the most points at the end of the season wins.

Live: https://wegopubnow.streamlit.app/ · In class it is presented through a mirrored iPhone or, on a laptop, inside the app's phone frame.

## Audience and mood
- Students, 20–26, out in the evening in Bairro Alto, Cais do Sodré and on the Nova campus.
- Playful and social, but **clean and calm**: little text, large tap targets, no slogans.
- A Lisbon feel: the yellow tram, azulejos, night atmosphere.

## The app (mobile first, iPhone format)
A bottom bar with 5 tabs; round **Profile** and **Lobbies** buttons in the top-right corner of every page.

| Tab | Content |
|---|---|
| **Map** | Full-screen map with 48 territories (blue = mine, red = rival, grey = free). At the top a bar with the lobby and the score; a *Location* switch. At the bottom a slim card "You are in …" with a tug-of-war bar. |
| **Ranks** | The season leaderboard (podium for places 1–3, a list below). |
| **+ Check in** | Camera first, then on **one** screen: large photo, drink and size as small pills, points, location, *Submit*. Then the result and *Go to map*. |
| **Games** | Minigames as a tile grid: Chug Duel, Reaction Duel, Quiz Duel, Time Duel. |
| **Activity** | *Feed* (check-ins, territory captures, duel results, medals) and *Photos*: a gallery like a phone's memories, a grid by game night, *All / Mine*; tapping a photo opens it almost full screen. |

Further pages: Profile (friends, statistics, account, Location switch), Lobbies, and login with a **start screen**.

## Design system (existing)
- **Typefaces:** *Anton* (headings, large and narrow), *Barlow* (text and buttons). The "WeGoPub" wordmark is set in Barlow 800, with "Pub" in red.
- **Colours:** navy `#142B3D` (text), background `#F8FAFC`, sky blue `#2C99D6` (accent, "mine"), red `#EB2F33` (brand, "rival"), grey `#8A97A6` (free).
- **Shapes:** rounded corners (pills, 16–24 px radius), white semi-transparent glass surfaces with blur over the map, soft shadows.
- **Icons:** Phosphor (line icons), filled for the active tab.
- All values live in `assets/theme.css`, the rules in `docs/DESIGN_GUIDELINES.md`.

## Constraints
- Built with **Streamlit** (Python). Styling is done with CSS and HTML; custom animations are possible only in CSS.
- Must work on iPhones from 375 to 430 px wide, with check-in and map without scrolling.
- Photos and fonts need a **free licence** or our own rights (the repository and the app are public).

## In progress / open for ideas
- **Start screen (done):** light background, "WP" app icon in sky blue, wordmark "WeGo" in navy + "Pub" in blue, at the bottom *Create account* (blue) and *Log in* (text). A short entrance (the icon pops, the wordmark slides up), otherwise calm. It appears once each time the app is opened: a player who is still signed in sees the icon and wordmark with "Tap to continue", and a tap anywhere continues to the map.
- Bring the Profile and Lobby pages visually in line with Map, Ranks and Photos.
- Small loading animations and empty states ("no photos yet", etc.).
