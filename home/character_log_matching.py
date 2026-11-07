"""Bounded historical matching and the bot's duration reward schedule."""
from datetime import date
from difflib import SequenceMatcher
import re

from .character_log_workbook import folded
from .master_legacy import _master_name, quest_local_date
from .master_mission_archive import active_seconds
from .master_roster import _history_title

NEAR_DAYS = 7
ROUNDING_MINUTES = 20
STAGES = ((150, 1), (300, 2), (450, 3), (600, 4), (900, 6), (1200, 8))


def candidates_for(entry, quests, masters):
    title = _history_title(entry['title'])
    exact = [q for q in quests if _history_title(q.name) == title]
    if exact:
        return exact
    try:
        day = date.fromisoformat(entry.get('date') or '')
    except ValueError:
        return []
    name = _master_name(entry.get('master'))
    if not name:
        return []
    ids = {discord for label, discord in masters if _master_name(label) == name and discord}
    def chapters(text):
        return re.findall(r'\b(?:\d+|[ivxlcdm]+)\b', text)
    return [q for q in quests if
        (_master_name(q.questMaster) == name or q.questMaster in ids) and
        any(d and abs((day - d).days) <= NEAR_DAYS for d in
            (quest_local_date(q.questDate), quest_local_date(q.endDate) if q.endDate else None)) and
        chapters(title) == chapters(_history_title(q.name)) and
        SequenceMatcher(None, title, _history_title(q.name), autojunk=False).ratio() >= .8]


def reward_for(entry, quest, player):
    amount = (player or {}).get('rewardAmount')
    source = 'bot_player'
    if type(amount) is not int:
        amount, source = quest.rewardAventurasOverride, 'bot_mission'
    boost = folded(entry.get('declared_rewards', {}).get('boost_spent')) in ('sim', 'true', '1', 'yes')
    declared = entry.get('adventures')
    rounded = False
    if type(amount) is not int:
        seconds, complete = active_seconds(getattr(quest, 'timeEvents', []))
        if not complete or seconds <= 0:
            return None, {'quantity_source': 'missing_duration'}
        minutes = seconds // 60
        amount = max((n for threshold, n in STAGES if minutes >= threshold), default=0)
        if minutes > 1200:
            amount += ((minutes - 1200) // 600) * 4
        source = 'active_duration'
        upcoming = next(((t, n) for t, n in STAGES if t > minutes), None)
        if upcoming is None:
            upcoming = (1200 + ((minutes - 1200) // 600 + 1) * 600, amount + 4)
        if 0 < upcoming[0] - minutes <= ROUNDING_MINUTES and declared in (
                upcoming[1], upcoming[1] * 2 if boost else upcoming[1]):
            amount, rounded = upcoming[1], True
    if type(amount) is not int or not 0 <= amount <= 100000:
        return None, {'quantity_source': 'invalid_recorded_amount'}
    multiplier = 2 if boost and declared == amount * 2 and amount > 0 else 1
    return amount * multiplier, {'quantity_source': source, 'base_adventures': amount,
                                'multiplier': multiplier, 'rounded': rounded}
