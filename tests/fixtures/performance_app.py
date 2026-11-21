"""Manual navigation QA with synthetic records and 50 ms simulated reads.

Run separately: streamlit run tests/fixtures/performance_app.py
Uses the actual pages/bootstrap. Never opens shared Supabase or changes real data.
"""
from pathlib import Path
import sys
from datetime import timedelta
from io import BytesIO
from time import sleep
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import streamlit as st
from PIL import Image
import data.db as db
import device_login
import shared
import phone_location
from streamlit.commands.execution_control import switch_page as native_switch_page
from core.models import Player, Lobby, LobbyMembership
from tests.test_scoring_v1 import START, entry, season
from tests.test_checkins import TERRITORY

st.set_page_config(page_title='WeGoPub · Navigation QA')
game=season()
game.ends_at=START+timedelta(days=30)
player=Player('player','Mia','Test','Only','fixture','mia@example.invalid')
member=LobbyMembership('member',player.id,game.lobby_id,START)
lobby=Lobby(game.lobby_id,'Navigation QA','LOCALONLY')
entries=[entry(f'photo-{i}','member','beer','small',i) for i in range(25)]
image=BytesIO()
Image.new('RGB',(32,24),'#edf2f4').save(image,'JPEG')
photo=image.getvalue()
reads=[]

def delayed(value):
    def read(*args,**kwargs):
        start=perf_counter()
        sleep(0.05)
        result=value() if callable(value) else value
        reads.append(round((perf_counter()-start)*1000,2))
        return result
    return read

db.get_client=lambda:(_ for _ in ()).throw(RuntimeError('Shared database disabled in local QA'))
db.get_player=delayed(player)
db.membership_context=delayed((member,game))
db.pending_minigame_invite_count=delayed(0)
db.list_memberships_for_player=delayed([member])
db.list_memberships_for_lobby=delayed([member])
db.list_lobbies=delayed([lobby])
db.list_lobbies_for_ids=delayed([lobby])
db.pending_lobby_invitations=delayed([])
db.get_lobby=delayed(lobby)
db.list_seasons_for_lobby=delayed([game])
db.list_seasons_for_lobbies=delayed([game])
db.list_membership_history_for_players=delayed([member])
db.list_drink_entries_for_seasons=lambda ids: delayed([])() if ids else []
db.list_transfers_for_seasons=delayed([])
db.list_drink_entries=delayed(entries)
db.list_drink_entries_for_membership=delayed(entries)
db.list_season_transfers=delayed([])
db.list_public_usernames=delayed([{'id':player.id,'display_name':player.display_name}])
db.list_friendships=delayed([])
db.profile_medal_launch=delayed(START)
db.list_chug_duels=delayed([])
db.pending_minigame_invites=delayed({})
db.download_profile_picture=delayed(None)
db.download_profile_pictures=delayed({})
db.membership_display_name=delayed('Mia')
db.list_membership_names=lambda pairs:(sleep(0.05),{pair:{'player_id':player.id,'display_name':'Mia'} for pair in pairs})[1]
db.profile_picture_access=delayed([])
db.list_checkin_photos=delayed(lambda:[dict(id=e.id,username='Mia',player_id=player.id,
    captured_at=None,submitted_at=e.submitted_at.isoformat(),is_owner=False,has_photo=True,
    timezone_name=game.timezone_name,rule_version='v1',entry=e,season=game,
    corrected_at=None,income_recipient=None,location='matched',territory=TERRITORY.name)
    for e in reversed(entries)])
db.download_checkin_photo=delayed(photo)
db.download_checkin_photos=lambda p,l,ids,**kwargs:delayed({eid:photo for eid in ids})()
db.list_checkin_revisions=delayed([])
shared.get_territories=lambda:[TERRITORY]
shared.sync_storage=lambda:''
phone_location.track_location=lambda:None
phone_location.location_switch=lambda **kwargs:None
device_login.sync_storage=lambda:''
def switch_page(target):
    if isinstance(target,str) and target.startswith('pages/'):
        target=str(Path(__file__).resolve().parents[2]/target)
    native_switch_page(target)
st.switch_page=switch_page
st.session_state.update(player_id=player.id,credential_version=player.pin_hash,
    current_membership_id=member.id,current_lobby_id=lobby.id,current_season_id=game.id,
    current_lobby_name=lobby.name,current_lobby_mode='individual',_lobby_restored_for=player.id,
    _location_asked=True,_remember_attempted=True)
st.caption('LOCAL QA · Synthetic data · 50 ms per read · Shared database disabled')
st.session_state['_qa_reads']=reads
requested=st.query_params.get('qa_page','profile')
page=st.navigation([st.Page(str(Path(__file__).resolve().parents[2]/'pages'/filename),
    title=title,url_path=route,default=route==requested) for title,route,filename in [
    ('Profile','profile','1_Profile.py'),('Lobbies','lobby','2_Lobby.py'),
    ('Photo history','check_in_photos','6_Check_in_photos.py'),
    ('Leaderboard','standings','4_Standings.py'),('Map','map','5_Map.py'),
    ('Check in','check_in','3_Check_in.py'),('Minigames','minigames','7_Minigames.py'),
    ('Activity','activity','8_Activity.py')]],position='hidden')
page.run()
