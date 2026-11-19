"""Synthetic local Time Duel app. Never uses Supabase credentials."""
import json,sys
from pathlib import Path
from urllib.request import Request,urlopen
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
import streamlit as st
import data.db as db
from core.models import Lobby,LobbyMembership
from tests.test_scoring_v1 import START,season
from time_duel_ui import render_time

st.set_page_config(page_title='Time Duel local test',layout='centered')
root=Path(__file__).resolve().parents[2]
st.markdown('<style>'+(root/'assets/theme.css').read_text()+(root/'assets/minigames.css').read_text()+'</style>',unsafe_allow_html=True)


def request(payload):
    with urlopen(Request('http://127.0.0.1:8781',json.dumps(payload).encode(),{'Content-Type':'application/json'}),timeout=15) as response:
        result=json.load(response)
    if 'error' in result:raise ValueError(result['error'])
    return result


db._time_rpc=lambda name,parameters:request(dict(name=name,parameters=parameters))
info=request(dict(name='fixture'));p=int(st.query_params.get('player','1'))-1
members=[LobbyMembership(mid,info['players'][i],info['lid'],START) for i,mid in enumerate(info['mids'])]
labels={m.id:'Player '+str(i+1) for i,m in enumerate(members)}
game=season();game.id=info['sid'];game.lobby_id=info['lid']
lobby=Lobby(info['lid'],'Synthetic Time Duel','LOCAL')


@st.fragment(run_every='1s')
def app():render_time(info['players'][p],info['mids'][p],lobby,game,members,labels)


app()
