"""Read-only service audit. Logs timings/counts/sizes, never identities or secrets.

python scripts/audit_app_performance.py --live --external --output .venv/audit-before.json
Live mode reads existing data and at most twelve authorized photos; it never writes records,
uploads objects, sends email, or displays/persists photo bytes. Use isolated tests
for writes and email delivery. Timings are from this machine, not Cloud internals.
"""
import argparse
from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
from statistics import median
import sys
from threading import Lock
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import httpx


def route(url):
    parts=url.path.strip('/').split('/')
    if '/rest/v1/rpc/' in url.path:
        return 'Supabase RPC: '+parts[3]
    if '/rest/v1/' in url.path:
        return 'Supabase table: '+parts[2]
    if '/storage/v1/bucket' in url.path:
        return 'Supabase Storage metadata'
    if '/storage/v1/object' in url.path:
        return 'Supabase Storage object'
    return url.host


@contextmanager
def requests_trace():
    original=httpx.Client.send
    records=[]
    lock=Lock()
    def send(client, request, *args, **kwargs):
        start=perf_counter()
        try:
            response=original(client,request,*args,**kwargs)
        except Exception:
            with lock: records.append((route(request.url),0,0,(perf_counter()-start)*1000))
            raise
        size=len(response.content) if response.is_stream_consumed else 0
        with lock: records.append((route(request.url),response.status_code,size,(perf_counter()-start)*1000))
        return response
    httpx.Client.send=send
    try: yield records
    finally: httpx.Client.send=original


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live',action='store_true')
    parser.add_argument('--external',action='store_true')
    parser.add_argument('--samples',type=int,default=5)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    if not 1<=args.samples<=10: parser.error('Use 1–10 samples.')
    report={'measured_at_utc':datetime.now(timezone.utc).isoformat(),'operations':{},'notes':[]}
    def measure(label,fn,samples=None):
        durations=[];counts=[];sizes=[];errors=[];routes=Counter();last=None
        for _ in range(samples or args.samples):
            with requests_trace() as trace:
                start=perf_counter()
                try:
                    last=fn()
                    durations.append(round((perf_counter()-start)*1000,2))
                except Exception as error: errors.append(type(error).__name__+':'+str(getattr(error,'code','')))
            counts.append(len(trace));sizes.append(sum(row[2] for row in trace));routes.update(row[0] for row in trace)
        item={'samples':len(counts),'successful_samples':len(durations),
              'median_ms':round(median(durations),2) if durations else None,'max_ms':max(durations) if durations else None,
              'request_count_range':[min(counts),max(counts)],'median_response_bytes':median(sizes),
              'request_routes':dict(routes),'errors':errors}
        report['operations'][label]=item
        print(label,json.dumps(item),flush=True)
        return last
    if args.live:
        import data.db as db
        client=db.get_client()
        measure('Supabase first REST request',lambda:client.table('players').select('id').limit(1).execute(),1)
        candidates=(client.table('lobby_memberships').select('id,player_id,lobby_id,lobbies!inner(seasons!inner(id))')
                    .is_('left_at','null').limit(100).execute().data)
        metadata=db._all_rows(lambda:client.table('drink_entries').select('season_id').order('id'))
        counts=Counter(row['season_id'] for row in metadata)
        pairs=[(m,s['id']) for m in candidates for s in m['lobbies']['seasons']]
        if pairs:
            m,sid=max(pairs,key=lambda pair:counts[pair[1]])
            pid,lid=m['player_id'],m['lobby_id']
            player=measure('Account validation',lambda:db.get_player(pid))
            measure('Membership and season',lambda:db.membership_context(pid,m['id'],lid,sid))
            measure('Public username directory',db.list_public_usernames)
            measure('Lobby directory',db.list_lobbies)
            measure('Season history',lambda:db.list_drink_entries(sid))
            measure('Season stake ledger',lambda:db.list_season_transfers(sid))
            measure('Invitation badge',lambda:db.pending_minigame_invite_count(pid,sid))
            photos=measure('Photo history metadata',lambda:db.list_checkin_photos(pid,lid))
            measure('Photo bucket metadata',db._private_photo_bucket)
            if photos:
                chosen=next((p for p in photos if p['has_photo']),None)
                if chosen:
                    measure('Authorized photo download',lambda:len(db.download_checkin_photo(pid,lid,chosen['id']) or b''),3)
                from parallel import run_parallel
                visible=[p['id'] for p in photos[:12]]
                measure('Visible gallery individual downloads',lambda:run_parallel(
                    *[lambda eid=eid:len(db.download_checkin_photo(pid,lid,eid) or b'') for eid in visible]),3)
                if hasattr(db,'download_checkin_photos'):
                    downloaded=measure('Visible gallery batched downloads',lambda:db.download_checkin_photos(pid,lid,visible),3)
                    if downloaded:
                        report['gallery_result']={'requested':len(visible),'available':sum(raw is not None for raw in downloaded.values())}
                        from photo_history_ui import photo_thumbnail
                        full=next((raw for raw in downloaded.values() if raw),None)
                        if full:
                            small=photo_thumbnail(full)
                            report['media_sample']={'original_bytes':len(full),'thumbnail_bytes':len(small or b'')}
            measure('Own profile picture',lambda:len(db.download_profile_picture(pid,player.pin_hash,pid) or b''),3)
            report['dataset']={'selected_season_entries':counts[sid],'visible_photos':len(photos or []),
                               'current_memberships_sampled':len(candidates)}
        else: report['notes'].append('No current membership/season available.')
    if args.external:
        with httpx.Client(timeout=15,follow_redirects=True) as client:
            for label,url in [
                ('Public app HTTP shell','https://wegopubnow.streamlit.app/'),
                ('CARTO map style','https://basemaps.cartocdn.com/gl/dark-matter-nolabels-gl-style/style.json'),
                ('Google Fonts CSS','https://fonts.googleapis.com/css2?family=Anton&family=Barlow:wght@400;500;600;700;800&display=swap'),
                ('Brevo connectivity only (unauthenticated)','https://api.brevo.com/v3/account')]:
                response=measure(label,lambda u=url:client.get(u),3)
                if response is not None:
                    report['operations'][label]['http_status']=response.status_code
                    if label=='CARTO map style' and response.status_code==200:
                        style=response.json()
                        source=next((s.get('url') for s in style.get('sources',{}).values() if s.get('url')),None)
                        if source:
                            tiles=measure('CARTO tile manifest',lambda:client.get(source),3)
                            report['operations']['CARTO tile manifest']['http_status']=tiles.status_code
    report['notes'] += ['No writes, email sends or permission changes performed.',
        'Five warm operation samples unless stated otherwise; this is not a phone or deployed WebSocket benchmark.',
        'Brevo 401 only verifies reachability; email delivery must be tested with mocked transport or a separately approved recipient.']
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(report,indent=2),encoding='utf-8')
        print('Saved timing-only audit report.',flush=True)


if __name__=='__main__': main()
