// Run with the synthetic minigame_lobbies_app.py fixture on port 8790.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {chromium} = require(path.resolve(process.argv[2]));
const output = path.resolve('.venv/minigame-previews');
fs.mkdirSync(output, {recursive: true});

async function checkSpacing(page) {
  const gaps = await page.evaluate(() => {
    const tags = document.querySelector('.duel-tags').getBoundingClientRect();
    const setup = document.querySelector('[class*="st-key-duel_setup_"]').getBoundingClientRect();
    const heading = document.querySelector('.duel-setup-heading').getBoundingClientRect();
    const firstField = document.querySelector('[class*="st-key-duel_setup_"] [data-testid="stRadio"]').getBoundingClientRect();
    const guide = document.querySelector('.duel-guide').getBoundingClientRect();
    const rules = document.querySelector('[data-testid="stExpander"]').getBoundingClientRect();
    return {tagsToCard: setup.top - tags.bottom, headingToField: firstField.top - heading.bottom,
      cardToGuide: guide.top - setup.bottom, guideToRules: rules.top - guide.bottom};
  });
  for (const [name, gap] of Object.entries(gaps)) {
    const minimum = name === 'tagsToCard' || name === 'guideToRules' ? 31 : 11;
    assert(gap >= minimum, `${name} needs at least ${minimum}px, got ${gap}px`);
  }
}

(async () => {
  const launch = {headless: true};
  if (process.env.MINIGAME_BROWSER_CHANNEL) launch.channel = process.env.MINIGAME_BROWSER_CHANNEL;
  else if (!fs.existsSync(chromium.executablePath())) launch.channel = 'msedge';
  const browser = await chromium.launch(launch);
  try {
    for (const dark of [false, true]) {
      for (const game of ['chug_duel', 'reaction', 'quiz', 'time']) {
        const page = await browser.newPage({viewport: {width: 390, height: 844}});
        await page.goto(`http://127.0.0.1:8790/?game=${game}&dark=${dark ? 1 : 0}`);
        await page.getByRole('button', {name: 'Challenge', exact: true}).waitFor();
        await page.getByRole('radio', {name: 'Jamie', exact: true}).waitFor();
        if (game === 'chug_duel') await page.getByRole('radio', {name: 'Large', exact: true}).waitFor();
        if (game === 'reaction' || game === 'quiz') await page.getByRole('radio', {name: '10', exact: true}).waitFor();
        await page.locator('.duel-guide').waitFor();
        await page.evaluate(() => document.fonts.ready);
        await checkSpacing(page);
        assert.equal(await page.locator('.duel-guide li').count(), 3);
        assert.equal(await page.getByText('Recent matches', {exact: true}).count(), 1);
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
        if (game === 'reaction' || game === 'quiz') {
          const targets = await page.locator(`[class*="st-key-pill_radio_${game}_stake"] [data-testid="stRadioOption"]`)
            .evaluateAll(elements => elements.map(el => el.getBoundingClientRect().width));
          assert(targets.every(width => width >= 44), 'Stake options must remain easy to tap');
        }
        const colors = await page.locator('.stApp').evaluate(el => ({
          bg: getComputedStyle(el).getPropertyValue('--bg').trim(),
          font: getComputedStyle(el).fontFamily,
        }));
        assert.equal(colors.bg, dark ? '#0E1A24' : '#F8FAFC');
        assert.match(colors.font, /Barlow/);
        await page.screenshot({path: path.join(output, `${game}-${dark ? 'dark' : 'light'}.png`), fullPage: true, animations: 'disabled'});
        await page.getByText('Recent matches', {exact: true}).click();
        await page.getByText('No matches yet. Your duels will appear here.', {exact: true}).waitFor({state: 'visible'});
        await page.getByText('No matches yet. Your duels will appear here.', {exact: true}).scrollIntoViewIfNeeded();
        await page.locator('[data-testid="stMain"]').evaluate(el => el.scrollTo(0, el.scrollHeight));
        const historyBox = await page.locator('.duel-history-empty').boundingBox();
        const navBox = await page.locator('.st-key-wego_bottom_nav').boundingBox();
        assert(historyBox.y + historyBox.height < navBox.y, 'History must be readable above the fixed navigation');
        await page.screenshot({path: path.join(output, `${game}-${dark ? 'dark' : 'light'}-guide.png`), animations: 'disabled'});
        await page.setViewportSize({width: 1280, height: 900});
        await page.locator('[data-testid="stMain"]').evaluate(el => el.scrollTo(0, 0));
        await checkSpacing(page);
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
        await page.screenshot({path: path.join(output, `${game}-${dark ? 'dark' : 'light'}-desktop.png`), fullPage: true, animations: 'disabled'});
        await page.close();
      }
    }

    // Exercise the real Time Duel board without changing its timing or bridge protocol.
    const page = await browser.newPage({viewport: {width: 390, height: 844}});
    await page.goto('http://127.0.0.1:8790/?game=time');
    const html = fs.readFileSync('components/time_duel/index.html', 'utf8');
    const theme = fs.readFileSync('assets/theme.css', 'utf8');
    const tokens = theme.slice(theme.indexOf('@import '), theme.indexOf('/* Base */'));
    await page.setContent(html);
    const duel = {id: 'visual-time', challenger_id: 'a', opponent_id: 'b', status: 'accepted',
      round_no: 0, target_ms: null, started_at: null, rounds: [
        {round_no: 0, membership_id: 'a', ready: false, elapsed_ms: null, started: false, abandoned: false},
        {round_no: 0, membership_id: 'b', ready: false, elapsed_ms: null, started: false, abandoned: false},
      ]};
    const args = {duel, member: 'a', challenger: 'Alex', opponent: 'Jamie', tokens};
    await page.evaluate(args => {
      window.events = [];
      window.addEventListener('message', e => {
        if (e.data?.type === 'streamlit:setComponentValue') window.events.push(e.data.value);
      });
      window.postMessage({type: 'streamlit:render', args}, '*');
    }, args);
    await page.getByRole('button', {name: "I'm ready", exact: true}).waitFor();
    assert.equal(await page.locator('#target').isHidden(), true);
    await page.screenshot({path: path.join(output, 'time-board-ready.png')});
    await page.getByRole('button', {name: "I'm ready", exact: true}).click();
    await page.waitForFunction(() => window.events.at(-1)?.action === 'ready');
    const ready = await page.evaluate(() => window.events.at(-1));
    assert.equal(ready.action, 'ready');
    args.acknowledgement = ready.event_id;
    duel.status = 'playing'; duel.target_ms = 7000; duel.started_at = new Date().toISOString();
    await page.evaluate(args => window.postMessage({type: 'streamlit:render', args}, '*'), args);
    await page.getByRole('button', {name: 'Start', exact: true}).click();
    await page.waitForFunction(() => window.events.at(-1)?.action === 'start');
    assert.equal(await page.locator('#target').textContent(), '?');
    await page.screenshot({path: path.join(output, 'time-board-running.png')});
    await page.getByRole('button', {name: 'Stop', exact: true}).click();
    const events = await page.evaluate(() => window.events);
    // Start remains at the front of the queue until its server acknowledgement.
    assert.equal(events.at(-1).action, 'start');
    args.acknowledgement = events.at(-1).event_id;
    duel.rounds[0].started = true;
    await page.evaluate(args => window.postMessage({type: 'streamlit:render', args}, '*'), args);
    await page.waitForFunction(() => window.events.at(-1)?.action === 'stop');
    assert.equal(Number.isInteger(await page.evaluate(() => window.events.at(-1).elapsed_ms)), true);
    for (const width of [320, 390, 1280]) {
      await page.setViewportSize({width, height: 700});
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    }
    await page.close();
    console.log('PASS: all four lobbies, mobile/desktop spacing, light/dark, empty histories; Time Duel Ready/Start/Stop and hidden timer.');
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exit(1); });
