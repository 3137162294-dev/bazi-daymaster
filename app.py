from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, JSONResponse
from datetime import datetime, date
import math

app = FastAPI()

# ── BaZi Calculation ──────────────────────────────────────────────

HEAVENLY_STEMS = ["Jia","Yi","Bing","Ding","Wu","Ji","Geng","Xin","Ren","Gui"]
HEAVENLY_STEMS_CN = ["甲","乙","丙","丁","戊","己","庚","辛","壬","癸"]
EARTHLY_BRANCHES = ["Zi","Chou","Yin","Mao","Chen","Si","Wu","Wei","Shen","You","Xu","Hai"]
EARTHLY_BRANCHES_CN = ["子","丑","寅","卯","辰","巳","午","未","申","酉","戌","亥"]
FIVE_ELEMENTS = {
    "Jia":"Wood (Yang)","Yi":"Wood (Yin)",
    "Bing":"Fire (Yang)","Ding":"Fire (Yin)",
    "Wu":"Earth (Yang)","Ji":"Earth (Yin)",
    "Geng":"Metal (Yang)","Xin":"Metal (Yin)",
    "Ren":"Water (Yang)","Gui":"Water (Yin)",
}
ANIMALS = {
    "Zi":"Rat","Chou":"Ox","Yin":"Tiger","Mao":"Rabbit",
    "Chen":"Dragon","Si":"Snake","Wu":"Horse","Wei":"Goat",
    "Shen":"Monkey","You":"Rooster","Xu":"Dog","Hai":"Pig",
}

# 2000-01-01 = 戊午 = index 54
DAY_PILLAR_REF_DATE = date(2000, 1, 1)
DAY_PILLAR_REF_INDEX = 54  # 戊午

# UTC offset for each timezone (standard time, ignoring DST for MVP)
TZ_UTC_OFFSETS = {
    "America/New_York": -5, "America/Chicago": -6, "America/Denver": -7,
    "America/Los_Angeles": -8, "America/Vancouver": -8, "America/Toronto": -5,
    "Europe/London": 0, "Europe/Paris": 1, "Europe/Berlin": 1,
    "Australia/Sydney": 10, "Asia/Tokyo": 9, "Asia/Seoul": 9,
    "Asia/Singapore": 8, "Asia/Kolkata": 5.5, "Asia/Dubai": 4,
    "Pacific/Auckland": 12, "America/Sao_Paulo": -3,
    "America/Mexico_City": -6, "Africa/Johannesburg": 2,
    "Asia/Shanghai": 8,
}

LNG_DEFAULTS = {
    "America/New_York": -74, "America/Chicago": -87.6, "America/Denver": -105,
    "America/Los_Angeles": -118, "America/Vancouver": -123, "America/Toronto": -79.4,
    "Europe/London": -0.1, "Europe/Paris": 2.3, "Europe/Berlin": 13.4,
    "Australia/Sydney": 151.2, "Asia/Tokyo": 139.7, "Asia/Seoul": 127,
    "Asia/Singapore": 103.8, "Asia/Kolkata": 77.2, "Asia/Dubai": 55.3,
    "Pacific/Auckland": 174.8, "America/Sao_Paulo": -46.6,
    "America/Mexico_City": -99.1, "Africa/Johannesburg": 28,
    "Asia/Shanghai": 116.4,  # Beijing area default; users should adjust
}


def day_pillar_from_date(d: date) -> tuple[str, str, int]:
    """Return (stem_en, branch_en, sexagenary_index) for a given Gregorian date."""
    delta = (d - DAY_PILLAR_REF_DATE).days
    idx = (DAY_PILLAR_REF_INDEX + delta) % 60
    return HEAVENLY_STEMS[idx % 10], EARTHLY_BRANCHES[idx % 12], idx


def hour_pillar(hour: int, minute: int, day_stem_idx: int, timezone_str: str, longitude: float) -> tuple[str, str, int]:
    """Return (stem_en, branch_en, solar_adjusted_hour) for the hour pillar using true solar time."""
    utc_offset = TZ_UTC_OFFSETS.get(timezone_str, 0)
    std_meridian = utc_offset * 15  # standard meridian for the timezone
    solar_correction = (longitude - std_meridian) * 4  # minutes
    total_minutes = hour * 60 + minute + solar_correction
    total_minutes = total_minutes % (24 * 60)
    solar_hour = int(total_minutes // 60)

    if solar_hour == 23 or solar_hour == 0:
        hb = 0   # 子
    elif solar_hour == 1 or solar_hour == 2:
        hb = 1   # 丑
    elif solar_hour == 3 or solar_hour == 4:
        hb = 2   # 寅
    elif solar_hour == 5 or solar_hour == 6:
        hb = 3   # 卯
    elif solar_hour == 7 or solar_hour == 8:
        hb = 4   # 辰
    elif solar_hour == 9 or solar_hour == 10:
        hb = 5   # 巳
    elif solar_hour == 11 or solar_hour == 12:
        hb = 6   # 午
    elif solar_hour == 13 or solar_hour == 14:
        hb = 7   # 未
    elif solar_hour == 15 or solar_hour == 16:
        hb = 8   # 申
    elif solar_hour == 17 or solar_hour == 18:
        hb = 9   # 酉
    elif solar_hour == 19 or solar_hour == 20:
        hb = 10  # 戌
    else:
        hb = 11  # 亥

    # Offset based on day stem (五鼠遁)
    offsets = [0, 2, 4, 6, 8, 0, 2, 4, 6, 8]
    hs = (hb + offsets[day_stem_idx]) % 10
    return HEAVENLY_STEMS[hs], EARTHLY_BRANCHES[hb], solar_hour


# ── Personality Descriptions ──────────────────────────────────────

DAY_MASTER_PROFILES = {
    "Jia": {
        "title": "The Giant Tree",
        "essence": "Jia Wood is a towering redwood — slow-growing, deeply rooted, built to last. You don't rush. You don't chase trends. You grow in one direction for decades, and one day people look up and realize you've become something they can't ignore.",
        "strengths": ["Visionary","Patient","Protective","Principled"],
        "shadow": "Stubborn to a fault. You'd rather break than bend — and sometimes you do break, because you refused to ask for help.",
        "advice": "Not every wind requires you to stand firm. Sometimes the strongest trees are the ones that know how to sway.",
    },
    "Yi": {
        "title": "The Living Vine",
        "essence": "Yi Wood is not the tree — it's the vine that weaves through the forest, finding paths where none exist. You don't break walls. You grow through the cracks. Your power isn't force — it's adaptability, charm, and knowing exactly which way to turn before anyone else does.",
        "strengths": ["Adaptable","Charming","Perceptive","Resilient"],
        "shadow": "You bend so easily that sometimes you forget which direction was yours. People trust your flexibility — until they wonder if you have a spine.",
        "advice": "Weaving through obstacles is a gift. Just make sure you're weaving toward something, not just around everything.",
    },
    "Bing": {
        "title": "The Sun Itself",
        "essence": "Bing Fire doesn't ask for attention — attention is what happens when you walk into a room. You radiate. People feel warmer around you, more alive, more seen. You're generous with your light, sometimes to people who never deserved it. But you can't help it — the Sun doesn't choose who it shines on.",
        "strengths": ["Radiant","Generous","Inspiring","Fearless"],
        "shadow": "You burn out. You give light to everyone else and forget that even the Sun needs to set sometimes. When you crash, you crash hard and you crash alone.",
        "advice": "The Sun at noon is blinding. The Sun at dawn is warm. Learn which one people need from you — and give yourself permission to be the dawn.",
    },
    "Ding": {
        "title": "The Candle in the Dark",
        "essence": "Ding Fire is not the Sun — it's the single flame in a dark room, the candle that burns steady when everything else has gone out. You don't overwhelm. You illuminate. People tell you things they've never told anyone else, because your light makes them feel safe enough to be seen.",
        "strengths": ["Intuitive","Discerning","Loyal","Quietly fierce"],
        "shadow": "You flicker. Your flame is sensitive to every draft — criticism, rejection, being misunderstood. You dim yourself before anyone else gets the chance to blow you out.",
        "advice": "A candle in the right place is worth more than a bonfire in the wrong one. Stop apologizing for not being louder.",
    },
    "Wu": {
        "title": "The Mountain",
        "essence": "Wu Earth is the mountain that doesn't move. You are steady, reliable, the person everyone leans on when everything else is falling apart. You don't react — you absorb. You don't chase — you wait. And when the storm passes, you're still standing there, exactly where you always were.",
        "strengths": ["Stable","Loyal","Grounded","Unshakable"],
        "shadow": "Mountains don't move — which means sometimes you stay in places that stopped being good for you years ago, because changing course feels like betraying who you are.",
        "advice": "Being reliable doesn't mean being immovable. Even mountains shift over time — they just do it slowly, and that's okay.",
    },
    "Ji": {
        "title": "The Fertile Soil",
        "essence": "Ji Earth is garden soil — rich, nourishing, ready to grow whatever seed is planted in it. You make things thrive. People, projects, ideas — put them in your care and they flourish. You see potential where others see dirt, and you have the patience to tend things until they bloom.",
        "strengths": ["Nurturing","Resourceful","Humble","Generous"],
        "shadow": "You give until the soil is depleted. You let too many people plant things in you, and one day you look up and realize none of what's growing was your own seed.",
        "advice": "The best gardens have boundaries. Not every seed deserves your soil. Choose what you grow.",
    },
    "Geng": {
        "title": "The Forged Blade",
        "essence": "Geng Metal is raw ore pulled from the earth and hammered into something sharp. You weren't born soft — you were forged. Every difficulty you've faced has been another strike of the hammer, and what's left is a blade that cuts through what others can't.",
        "strengths": ["Decisive","Disciplined","Courageous","Uncompromising"],
        "shadow": "You cut things that needed cutting — and also things that didn't. Not every problem is solved by force. Some things need a soft hand, and you don't have one.",
        "advice": "A sword is most powerful when it stays in its sheath until the right moment. Learn to choose your battles, not just win them.",
    },
    "Xin": {
        "title": "The Jewel",
        "essence": "Xin Metal is not raw ore — it's the finished product, the polished gem, the precision instrument. You're refined, discerning, and you have standards that most people find exhausting. You see details others miss. You demand quality. And when you commit to something, it's going to be done right or not at all.",
        "strengths": ["Refined","Precise","Articulate","Discerning"],
        "shadow": "Perfectionism is your prison. You judge yourself by standards you'd never impose on anyone else, and then you're surprised when you feel alone.",
        "advice": "A jewel doesn't need to be the biggest stone in the room. It just needs to catch the light in the right way.",
    },
    "Ren": {
        "title": "The Open Ocean",
        "essence": "Ren Water is not a river or a lake — it's the sea. Vast, deep, unknowable. You contain multitudes. People can sail on you for years and never reach your depths. You move between worlds easily — logic and intuition, solitude and connection, the surface and the abyss.",
        "strengths": ["Profound","Free-spirited","Wise","Boundless"],
        "shadow": "You drift. The ocean has no banks, and sometimes neither do you. You flow so freely that you lose track of where you were trying to go — or whether you were trying to go anywhere at all.",
        "advice": "Boundlessness is freedom. But even the ocean needs a shore to meet. Find yours.",
    },
    "Gui": {
        "title": "The Deep Spring",
        "essence": "Gui Water is not the ocean — it's the hidden spring, the underground stream, the still lake at dawn. You don't announce yourself. You don't need to. Your depth speaks for itself. You understand things before anyone explains them. You feel shifts in the emotional weather before the first cloud appears.",
        "strengths": ["Deeply intuitive","Mysterious","Healing","Imaginative"],
        "shadow": "You hide. You're so deep that people can't find you — including people who need you, including yourself. Your stillness can become stagnation before you notice.",
        "advice": "A spring that never reaches the surface might as well not exist. Let someone see your depth.",
    },
}


# ── HTML Frontend ──────────────────────────────────────────────────

HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Find Your Day Master — Chinese Destiny Analysis</title>
<style>
  *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
    background: linear-gradient(135deg, #0f0c29 0%, #1a1a3e 40%, #24243e 100%);
    min-height: 100vh;
    color: #e8e6f0;
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 2rem 1rem;
  }
  .container { max-width: 600px; width: 100%; }
  header { text-align: center; margin-bottom: 2.5rem; }
  header h1 {
    font-size: 2rem;
    font-weight: 700;
    background: linear-gradient(135deg, #f5af19, #f12711);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    margin-bottom: 0.5rem;
  }
  header p { color: #8b8a9e; font-size: 0.95rem; }
  .card {
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 16px;
    padding: 2rem;
    backdrop-filter: blur(10px);
    margin-bottom: 1.5rem;
  }
  label { display: block; font-size: 0.85rem; font-weight: 600; color: #a9a8c0; margin-bottom: 0.35rem; margin-top: 1rem; }
  label:first-of-type { margin-top: 0; }
  input, select {
    width: 100%;
    padding: 0.75rem 1rem;
    background: rgba(255,255,255,0.06);
    border: 1px solid rgba(255,255,255,0.12);
    border-radius: 10px;
    color: #fff;
    font-size: 1rem;
    font-family: inherit;
    outline: none;
    transition: border-color 0.2s;
  }
  input:focus, select:focus { border-color: #f5af19; }
  option { background: #1a1a3e; color: #fff; }
  button {
    width: 100%;
    margin-top: 1.5rem;
    padding: 0.9rem;
    background: linear-gradient(135deg, #f5af19, #f12711);
    border: none;
    border-radius: 10px;
    color: #fff;
    font-size: 1.1rem;
    font-weight: 700;
    cursor: pointer;
    transition: transform 0.15s, box-shadow 0.15s;
  }
  button:hover { transform: translateY(-1px); box-shadow: 0 8px 30px rgba(245,175,25,0.3); }
  button:active { transform: translateY(0); }
  button:disabled { opacity: 0.5; pointer-events: none; }
  .result { display: none; }
  .result.show { display: block; }
  .daymaster-badge {
    text-align: center;
    padding: 2rem 1rem;
    border-radius: 16px;
    margin-bottom: 1.5rem;
  }
  .daymaster-badge .stem {
    font-size: 4rem;
    font-weight: 900;
    background: linear-gradient(135deg, #f5af19, #f12711);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
  }
  .daymaster-badge .title { font-size: 1.3rem; font-weight: 700; margin-top: 0.25rem; }
  .daymaster-badge .element { font-size: 0.9rem; color: #8b8a9e; margin-top: 0.25rem; }
  .essence { font-size: 1.05rem; line-height: 1.7; color: #c9c7dd; margin-bottom: 1.5rem; }
  .traits { display: flex; flex-wrap: wrap; gap: 0.5rem; margin-bottom: 1.5rem; }
  .trait {
    background: rgba(245,175,25,0.12);
    color: #f5af19;
    padding: 0.4rem 0.9rem;
    border-radius: 20px;
    font-size: 0.85rem;
    font-weight: 600;
  }
  .shadow-box {
    background: rgba(241,39,17,0.08);
    border-left: 3px solid #f12711;
    padding: 1rem;
    border-radius: 0 10px 10px 0;
    margin-bottom: 1.5rem;
  }
  .shadow-box h4 { color: #f12711; margin-bottom: 0.35rem; font-size: 0.9rem; }
  .shadow-box p { color: #c9c7dd; font-size: 0.95rem; line-height: 1.6; }
  .advice {
    background: rgba(245,175,25,0.06);
    padding: 1rem;
    border-radius: 10px;
    font-style: italic;
    color: #f5af19;
    font-size: 0.95rem;
    line-height: 1.6;
  }
  .bazi-detail {
    background: rgba(255,255,255,0.03);
    border-radius: 12px;
    padding: 1.25rem;
    margin-top: 1rem;
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.75rem;
    font-size: 0.9rem;
  }
  .bazi-detail dt { color: #8b8a9e; }
  .bazi-detail dd { color: #e8e6f0; font-weight: 600; }
  .cta {
    margin-top: 1.5rem;
    text-align: center;
  }
  .cta a {
    color: #f5af19;
    font-weight: 600;
    text-decoration: underline;
  }
  .loading { text-align: center; display: none; padding: 2rem; }
  .loading.show { display: block; }
  .spinner {
    width: 40px; height: 40px;
    border: 3px solid rgba(255,255,255,0.1);
    border-top-color: #f5af19;
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
    margin: 0 auto 1rem;
  }
  @keyframes spin { to { transform: rotate(360deg); } }
  footer { text-align: center; margin-top: 2rem; color: #555; font-size: 0.8rem; }
</style>
</head>
<body>
<div class="container">
  <header>
    <h1>Find Your Day Master</h1>
    <p>Ancient Chinese Destiny Analysis — discover your core identity from your birth date.</p>
  </header>

  <div class="card" id="form-card">
    <label for="birthdate">Birth Date</label>
    <input type="date" id="birthdate" required>

    <label for="birthtime">Birth Time (local time)</label>
    <input type="time" id="birthtime" value="12:00" required>

    <label for="timezone">Your Timezone</label>
    <select id="timezone" onchange="updateLongitude()">
      <option value="America/New_York">Eastern Time (US)</option>
      <option value="America/Chicago">Central Time (US)</option>
      <option value="America/Denver">Mountain Time (US)</option>
      <option value="America/Los_Angeles">Pacific Time (US)</option>
      <option value="America/Vancouver">Pacific Time (Canada)</option>
      <option value="America/Toronto">Eastern Time (Canada)</option>
      <option value="Europe/London">London (UK)</option>
      <option value="Europe/Paris">Paris / Central Europe</option>
      <option value="Europe/Berlin">Berlin / Central Europe</option>
      <option value="Australia/Sydney">Sydney (Australia)</option>
      <option value="Asia/Tokyo">Tokyo (Japan)</option>
      <option value="Asia/Seoul">Seoul (Korea)</option>
      <option value="Asia/Singapore">Singapore</option>
      <option value="Asia/Kolkata">India</option>
      <option value="Asia/Dubai">Dubai (UAE)</option>
      <option value="Pacific/Auckland">Auckland (New Zealand)</option>
      <option value="America/Sao_Paulo">São Paulo (Brazil)</option>
      <option value="America/Mexico_City">Mexico City</option>
      <option value="Africa/Johannesburg">South Africa</option>
      <option value="Asia/Shanghai">China / Hong Kong / Taiwan</option>
    </select>

    <label for="longitude">Birth City Longitude <span style="font-weight:400;color:#8b8a9e;">(for true solar time)</span></label>
    <input type="number" id="longitude" step="0.1" placeholder="e.g. 121.6 for Dalian, -74 for NYC" required>

    <button onclick="calculate()">Reveal My Day Master</button>
  </div>

  <div class="loading" id="loading">
    <div class="spinner"></div>
    <p>Calculating your destiny...</p>
  </div>

  <div class="result" id="result">
    <div class="daymaster-badge" id="badge">
      <div class="stem" id="stem-display"></div>
      <div class="title" id="title-display"></div>
      <div class="element" id="element-display"></div>
    </div>
    <div class="card">
      <div class="essence" id="essence-display"></div>
      <div class="traits" id="traits-display"></div>
      <div class="shadow-box">
        <h4>Your Shadow Side</h4>
        <p id="shadow-display"></p>
      </div>
      <div class="advice" id="advice-display"></div>
      <dl class="bazi-detail" id="bazi-detail"></dl>
    </div>
    <div class="cta">
      <p>Want a full destiny report? <a href="#">Coming soon →</a></p>
    </div>
  </div>

  <footer>
    For entertainment purposes only. Based on traditional Chinese BaZi (Eight Characters) astrology.
  </footer>
</div>

<script>
const lngDefaults = {
  "America/New_York": -74, "America/Chicago": -87.6, "America/Denver": -105,
  "America/Los_Angeles": -118, "America/Vancouver": -123, "America/Toronto": -79.4,
  "Europe/London": -0.1, "Europe/Paris": 2.3, "Europe/Berlin": 13.4,
  "Australia/Sydney": 151.2, "Asia/Tokyo": 139.7, "Asia/Seoul": 127,
  "Asia/Singapore": 103.8, "Asia/Kolkata": 77.2, "Asia/Dubai": 55.3,
  "Pacific/Auckland": 174.8, "America/Sao_Paulo": -46.6,
  "America/Mexico_City": -99.1, "Africa/Johannesburg": 28,
  "Asia/Shanghai": 116.4,
};

function updateLongitude() {{
  const tz = document.getElementById('timezone').value;
  document.getElementById('longitude').value = lngDefaults[tz] || 0;
}}

// Set initial value
document.getElementById('longitude').value = lngDefaults[document.getElementById('timezone').value] || 0;

async function calculate() {{
  const birthdate = document.getElementById('birthdate').value;
  const birthtime = document.getElementById('birthtime').value;
  const timezone = document.getElementById('timezone').value;
  const longitude = document.getElementById('longitude').value;

  if (!birthdate) {{ alert('Please enter your birth date.'); return; }}
  if (!longitude) {{ alert('Please enter your birth city longitude.'); return; }}

  document.getElementById('form-card').style.display = 'none';
  document.getElementById('loading').classList.add('show');
  document.getElementById('result').classList.remove('show');

  try {
    const resp = await fetch('/api/daymaster', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ birthdate, birthtime, timezone, longitude }),
    });
    if (!resp.ok) throw new Error('Server error');
    const data = await resp.json();

    document.getElementById('stem-display').textContent = data.day_master;
    document.getElementById('title-display').textContent = data.profile.title;
    document.getElementById('element-display').textContent = data.five_element;
    document.getElementById('essence-display').textContent = data.profile.essence;
    document.getElementById('traits-display').innerHTML = data.profile.strengths.map(s => `<span class="trait">${s}</span>`).join('');
    document.getElementById('shadow-display').textContent = data.profile.shadow;
    document.getElementById('advice-display').textContent = data.profile.advice;
    document.getElementById('bazi-detail').innerHTML = `
      <dt>Day Pillar</dt><dd>${data.day_pillar_cn} / ${data.day_pillar}</dd>
      <dt>Hour Pillar</dt><dd>${data.hour_pillar_cn} / ${data.hour_pillar}</dd>
      <dt>Day Stem</dt><dd>${data.day_master} (${data.day_master_cn})</dd>
      <dt>Day Branch</dt><dd>${data.day_branch} — ${data.day_animal}</dd>
      <dt>Five Element</dt><dd>${data.five_element}</dd>
    `;

    document.getElementById('loading').classList.remove('show');
    document.getElementById('result').classList.add('show');
    document.getElementById('result').scrollIntoView({ behavior: 'smooth' });
  } catch (e) {
    document.getElementById('loading').classList.remove('show');
    document.getElementById('form-card').style.display = '';
    alert('Something went wrong. Please try again.');
  }
}
</script>
</body>
</html>
"""


# ── Routes ─────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index():
    return HTML


@app.post("/api/daymaster")
async def api_daymaster(data: dict):
    birthdate = data.get("birthdate")
    birthtime = data.get("birthtime", "12:00")
    timezone_str = data.get("timezone", "UTC")
    longitude = float(data.get("longitude", 0))

    d = date.fromisoformat(birthdate)
    parts = birthtime.split(":")
    h = int(parts[0])
    m = int(parts[1]) if len(parts) > 1 else 0

    # Day pillar may shift if solar correction crosses midnight
    utc_offset = TZ_UTC_OFFSETS.get(timezone_str, 0)
    std_meridian = utc_offset * 15
    solar_correction = (longitude - std_meridian) * 4
    total_minutes = h * 60 + m + solar_correction
    if total_minutes < 0:
        from datetime import timedelta
        d = d - timedelta(days=1)
    elif total_minutes >= 24 * 60:
        from datetime import timedelta
        d = d + timedelta(days=1)

    day_stem, day_branch, day_idx = day_pillar_from_date(d)
    day_stem_idx = HEAVENLY_STEMS.index(day_stem)

    hour_stem, hour_branch, solar_hour = hour_pillar(h, m, day_stem_idx, timezone_str, longitude)

    profile = DAY_MASTER_PROFILES.get(day_stem, DAY_MASTER_PROFILES["Jia"])

    return {
        "day_master": day_stem,
        "day_master_cn": HEAVENLY_STEMS_CN[day_stem_idx],
        "day_branch": day_branch,
        "day_animal": ANIMALS.get(day_branch, ""),
        "day_pillar": f"{day_stem} {day_branch}",
        "day_pillar_cn": f"{HEAVENLY_STEMS_CN[day_stem_idx]}{EARTHLY_BRANCHES_CN[day_idx % 12]}",
        "hour_pillar": f"{hour_stem} {hour_branch}",
        "hour_pillar_cn": f"{HEAVENLY_STEMS_CN[HEAVENLY_STEMS.index(hour_stem)]}{EARTHLY_BRANCHES_CN[EARTHLY_BRANCHES.index(hour_branch)]}",
        "five_element": FIVE_ELEMENTS.get(day_stem, ""),
        "profile": profile,
    }
