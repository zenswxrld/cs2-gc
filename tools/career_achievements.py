"""Finite, one-time career milestones. Achievement payouts never count toward star goals."""
import time
MAX=(1<<64)-1
DEFINITIONS=[]

def add(title,key,target,stars,category,description,icon='star'):
    DEFINITIONS.append(dict(id=key+':'+str(target),title=title,key=key,target=target,stars=stars,
                            category=category,description=description,icon=icon))

# Retain the original 13 IDs, order and thresholds for existing owned progress.
for row in (
 ('First finish','matches',1,5,'Career','Complete a local match. Leaving early does not count.'),
 ('Regular','matches',10,15,'Career','Complete 10 local matches.'),
 ('Seasoned','matches',100,75,'Career','Complete 100 local matches.'),
 ('Winning ways','wins',10,15,'Career','Reach 10 saved local Premier wins.'),
 ('Veteran','wins',100,75,'Career','Reach 100 saved local Premier wins.'),
 ('Five figures','rating',10000,30,'Career','Reach a local Premier rating of 10,000. The unlock is kept if your rating falls.'),
 ('Contender','rating',20000,60,'Career','Reach a local Premier rating of 20,000. The unlock is kept if your rating falls.'),
 ('Centurion','kills',100,10,'Combat','Get 100 kills during live play. Warmup and spectated bot kills do not count.'),
 ('Deadeye','headshots',50,10,'Combat','Get 50 headshot kills during live play.'),
 ('Most valuable','mvps',25,10,'Objectives','Earn 25 round MVP awards.'),
 ('Demolition','plants',10,10,'Objectives','Complete 10 bomb plants yourself. Interrupted plants and teammates do not count.'),
 ('Safe hands','defuses',10,10,'Objectives','Complete 10 bomb defuses yourself. Interrupted defuses do not count.'),
 ('Mission ready','missions',5,15,'Objectives','Complete all stages of five local missions. Each mission period counts once.'),
):add(*row)

for key,category,icon,description,tiers in (
 ('kills','Combat','kill','Get enemy kills during live play.',[(500,25,'On target'),(2500,50,'Battle tested'),(10000,150,'Ten thousand')]),
 ('headshots','Combat','headshot','Get headshot kills during live play.',[(250,25,'Precision'),(1000,50,'Sharpshooter'),(5000,150,'Head hunter')]),
 ('mvps','Objectives','star','Earn round MVP awards.',[(100,25,'Impact player'),(500,75,'Team cornerstone')]),
 ('plants','Objectives','bomb','Complete bomb plants yourself.',[(50,25,'Armed and ready'),(250,75,'Site specialist')]),
 ('defuses','Objectives','defuse','Complete bomb defuses yourself.',[(50,25,'Under pressure'),(250,75,'Bomb disposal')]),
 ('missions','Objectives','star','Complete every stage of a local mission. Each period counts once.',[(25,40,'Mission specialist'),(100,100,'Mission master')]),
 ('enemies_flashed','Utility','flash','Blind an enemy for at least 1 second with your flashbang. Each enemy counts once per flash; teammates and self-flashes do not count.',[(10,5,'Lights out'),(100,15,'Dazzling'),(500,40,'Flash specialist'),(2000,100,'Blinding presence')]),
 ('flash_assists','Utility','flash','Get a server-confirmed flash assist when a teammate kills an enemy you flashed. Your own kills are not assists.',[(10,5,'Set them up'),(50,15,'Perfect setup'),(250,50,'Team enabler')]),
 ('smoke_kills','Utility','smoke','Kill an enemy with a bullet the server marks as passing through a smoke grenade. Standing near smoke alone does not count.',[(10,10,'Through the haze'),(50,25,'Smoke reader'),(250,75,'Beyond the veil')]),
 ('blind_kills','Combat','flash','Kill an enemy while the server marks YOU as blinded by a flashbang. Killing a blinded enemy is a different action.',[(5,5,'Whiteout'),(25,15,'Blind faith'),(100,40,'Instinct')]),
 ('noscope_kills','Combat','sniper','Get a kill marked as a no-scope by the server.',[(5,5,'Off the scope'),(25,15,'Quick instinct'),(100,40,'Unscoped')]),
 ('wallbang_kills','Combat','kill','Kill an enemy after the bullet penetrates a surface, as confirmed by the server.',[(10,5,'Thin cover'),(50,15,'Penetration'),(250,50,'No safe cover')]),
 ('grenade_kills','Utility','grenade','Kill an enemy with your HE grenade. Damage without a kill does not count.',[(5,5,'Frag out'),(25,15,'Explosive entry'),(100,40,'Blast radius')]),
 ('fire_kills','Utility','molotov','Kill an enemy with your Molotov or incendiary fire.',[(5,5,'Burning point'),(25,15,'Area denied'),(100,40,'Playing with fire')]),
 ('knife_kills','Weapons','knife','Kill an enemy with a knife during live play.',[(5,5,'Close quarters'),(25,15,'Silent approach'),(100,40,'On the edge')]),
 ('taser_kills','Weapons','taser','Kill an enemy with the Zeus x27 during live play.',[(5,5,'High voltage'),(25,15,'Shock tactics'),(100,40,'Fully charged')]),
 ('stars','Career','star','Earn gameplay stars from kills, MVPs, objectives and completed matches. Achievement payouts, grants and purchases are excluded.',[(1000,10,'Pocket change'),(10000,40,'Star saver'),(50000,100,'Constellation')]),
 ('xp','Career','star','Earn local gameplay and mission XP.',[(10000,10,'Making progress'),(50000,30,'Experienced'),(250000,75,'Long service')]),
):
    for target,reward,title in tiers:add(title,key,target,reward,category,description,icon)

for key,name,icon in (('pistol_kills','Pistol','pistol'),('rifle_kills','Rifle','rifle'),('sniper_kills','Sniper','sniper'),
                      ('smg_kills','SMG','smg'),('shotgun_kills','Shotgun','shotgun'),('heavy_kills','Heavy','heavy')):
    for target,reward,rank in ((100,10,'proficiency'),(500,25,'specialist'),(2500,75,'mastery')):
        add(name+' '+rank,key,target,reward,'Weapons','Get enemy kills with weapons in the '+name.lower()+' class during live play.',icon)

GOALS=tuple((a['title'],a['key'],a['target']) for a in DEFINITIONS)
EVENT_KEYS=('enemies_flashed','flash_assists','smoke_kills','blind_kills','noscope_kills','wallbang_kills',
            'grenade_kills','fire_kills','knife_kills','taser_kills','pistol_kills','rifle_kills',
            'sniper_kills','smg_kills','shotgun_kills','heavy_kills')

def counts(state):
    combat=state.get('combat_stats') or {};premier=state.get('premier') or {}
    return dict(combat,matches=state.get('matches',0),wins=premier.get('wins',0),rating=premier.get('rating',0),
                missions=state.get('missions_completed',0),stars=state.get('gameplay_stars_earned',0),xp=state.get('total',0))

def unlocked(state):
    values=counts(state);done=set(state.get('local_achievements') or [])
    for a in DEFINITIONS:
        value=values.get(a['key'],0)
        if type(value) is int and value>=a['target']:done.add(a['id'])
    return sorted(done)

def award(state,enabled=True):
    done=set(unlocked(state));paid=state.setdefault('achievement_paid',{})
    if not isinstance(paid,dict):raise ValueError('Invalid achievement payment history')
    earned=0;recent=list(state.get('achievement_recent') or []);stamp=int(time.time())
    for a in DEFINITIONS:
        if a['id'] in done and a['id'] not in paid:
            amount=a['stars'] if enabled else 0
            paid[a['id']]=amount;earned+=amount
            recent.append(dict(id=a['id'],stars=amount,at=stamp))
    state['achievement_recent']=recent[-12:]
    state['local_achievements']=sorted(done)
    state['achievement_stars']=min(MAX,state.get('achievement_stars',0)+earned)
    state['mission_stars']=min(MAX,state.get('mission_stars',0)+earned)
    return earned


def recent_unlocks(state):
    known={a['id'] for a in DEFINITIONS};paid=state.get('achievement_paid') or {};seen=set();rows=[]
    for row in reversed(state.get('achievement_recent') or []):
        if not isinstance(row,dict):continue
        key=row.get('id');stamp=row.get('at');stars=paid.get(key)
        if not isinstance(key,str) or key not in known or key in seen or type(stamp) is not int or stamp<0 or type(stars) is not int:continue
        seen.add(key);rows.append(dict(id=key,stars=max(0,stars),at=stamp))
    return rows[:12]

def progress(state):
    values=counts(state);done=set(unlocked(state));paid=state.get('achievement_paid') or {}
    return [dict(a,progress=max(0,values.get(a['key'],0)),unlocked=a['id'] in done,paid=a['id'] in paid,
                 paid_stars=paid.get(a['id'],0)) for a in DEFINITIONS]
