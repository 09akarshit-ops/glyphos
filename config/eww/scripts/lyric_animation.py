"""Small, playback-independent lyric transition state."""
DURATION=.68

def identity(state):return (state.get('player'),state.get('title'),state.get('line'),state.get('active'),state.get('next'))
def transition(old,new):
 if not old or identity(old)==identity(new):return None
 if old.get('lyrics_mode') not in ('synced','plain') or new.get('lyrics_mode') not in ('synced','plain') or new.get('marquee'):return None
 promoted=old.get('next')==new.get('active') and bool(new.get('active'))
 return dict(old=old.get('active',''),active=new.get('active',''),next=new.get('next',''),promoted=promoted)
def frame(change,elapsed):
 t=max(0,min(1,elapsed/DURATION));p=t*t*t*(t*(6*t-15)+10)
 return dict(lyric_animating=t<1,lyric_old=change['old'],lyric_promoted=change['active'],lyric_following=change['next'],
  lyric_old_y=round(-24*p,3),lyric_active_y=round(24*(1-p),3),lyric_next_y=round(24+24*(1-p),3),
  lyric_old_alpha=round(1-p,4),lyric_active_alpha=round(p,4),lyric_next_alpha=0,lyric_active_size=18)
def settled():
 return dict(lyric_animating=False,lyric_old='',lyric_promoted='',lyric_following='',lyric_old_y=0,lyric_active_y=0,lyric_next_y=24,lyric_old_alpha=0,lyric_active_alpha=1,lyric_next_alpha=.4,lyric_active_size=18)
