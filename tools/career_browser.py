"""Grouped achievement navigation and a permanent details pane for native Panorama."""
SCRIPT=r'''
    const groups=[],recentCards=[];
    let selected=null,selectedTier=null,activeCategory='All',detail=null;
    const groupNames={matches:'Matches completed',wins:'Premier victories',rating:'Premier rating',kills:'Kills',
        headshots:'Headshots',mvps:'Most valuable player',plants:'Bomb plants',defuses:'Bomb defuses',missions:'Missions',
        enemies_flashed:'Enemies flashed',flash_assists:'Flash assists',smoke_kills:'Through-smoke kills',
        blind_kills:'Kills while blinded',noscope_kills:'No-scope kills',wallbang_kills:'Wallbang kills',
        grenade_kills:'HE grenade kills',fire_kills:'Fire kills',knife_kills:'Knife kills',taser_kills:'Zeus kills',
        stars:'Gameplay stars',xp:'Experience earned',pistol_kills:'Pistol mastery',rifle_kills:'Rifle mastery',
        sniper_kills:'Sniper mastery',smg_kills:'SMG mastery',shotgun_kills:'Shotgun mastery',heavy_kills:'Heavy mastery'};
    const tierColors=['#b48b64','#b4c4ce','#d0b974','#9ac7d1','#beb2dc'];
    function picture(parent,id,icon,size) {
        const p=$.CreatePanel('Image',parent,id);p.SetImage('file://{images}/icons/'+(icons[icon]||icons.star)+'.svg');
        p.style.width=size+'px';p.style.height=size+'px';return p;
    }
    function progressBar(parent,id) {
        const track=panel(parent,id,'right');track.style.width='100%';track.style.height='3px';track.style.marginTop='7px';track.style.backgroundColor='#ffffff13';
        const fill=panel(track,'','');fill.style.height='100%';return fill;
    }
    function setBar(fill,amount,target,done) {
        fill.style.width=(done?100:Math.min(100,Math.max(0,amount/target*100)))+'%';
        fill.style.backgroundColor=done?'#a3c28d':'#81a6ba';
    }
    function complete(a) {return a.unlocked||a.amount>=a.target;}
    function nextTier(g) {return g.tiers.filter(a=>!complete(a))[0]||g.tiers[g.tiers.length-1];}
    function roman(i) {return ['I','II','III','IV','V','VI'][i]||String(i+1);}
    function condition(a) {return a.description+'\nTarget: '+a.target+'. One-time reward: '+a.stars+' stars.';}
    function activate(p,fn) {p.SetPanelEvent('onactivate',fn);}
    function selectGroup(g,tier) {
        selected=g;selectedTier=tier||null;renderDetail();
        groups.forEach(item=>{item.panel.style.backgroundColor=item===g?'#ffffff0c':'#ffffff00';item.panel.style.borderLeft=item===g?'2px solid #72b5d8':'2px solid #ffffff00';});
    }
    function selectFilter(name) {
        activeCategory=name;
        filters.forEach(f=>{f.p.caption.style.color=f.key===name?'#e9f1f6':'#89959e';f.p.panel.style.backgroundColor=f.key===name?'#ffffff13':'#ffffff00';});
        groups.forEach(g=>g.panel.visible=name==='All'||g.category===name);
        if(!selected||!(name==='All'||selected.category===name)) {
            const first=groups.filter(g=>name==='All'||g.category===name)[0];if(first)selectGroup(first);
        }
    }
    function renderDetail() {
        if(!selected||!detail)return;
        const g=selected,a=selectedTier||nextTier(g),index=g.tiers.indexOf(a),done=complete(a);
        detail.icon.SetImage('file://{images}/icons/'+(icons[g.icon]||icons.star)+'.svg');
        detail.title.text=g.name;detail.category.text=g.category.toUpperCase()+'  /  '+g.tiers.filter(complete).length+' OF '+g.tiers.length+' TIERS';
        detail.tier.text='TIER '+roman(index)+' · '+a.title;detail.tier.style.color=tierColors[Math.min(index,4)];
        detail.description.text=a.description;detail.amount.text=done&&a.amount<a.target?'Target reached: '+a.target:Math.min(a.amount,a.target)+' / '+a.target;
        setBar(detail.fill,a.amount,a.target,done);
        detail.reward.text='+'+a.stars+' ★';
        detail.status.text=done?(a.paid?(a.paid_stars>0?'AWARDED · '+a.paid_stars+' STARS':'COMPLETED · STARS DISABLED'):'COMPLETED · REWARD PENDING'):(a.target-a.amount)+' remaining';
        detail.status.style.color=done?'#b9d2a8':'#aab8c1';
        if(detail.groupKey!==g.key) {
            detail.tiers.RemoveAndDeleteChildren();detail.rows=[];detail.groupKey=g.key;
            g.tiers.forEach((t,i)=>{
                const p=panel(detail.tiers,'CareerTier_'+g.key+'_'+i,'right');p.style.width='100%';p.style.padding='9px 8px';p.style.borderBottom='1px solid #ffffff0d';
                const badge=label(p,'',roman(i),16,tierColors[Math.min(i,4)]);badge.style.width='28px';
                const title=label(p,'',t.title,16);title.style.width='fill-parent-flow(1)';
                const status=label(p,'CareerTierStatus_'+g.key+'_'+i,'',13,'#aab8c1');status.style.marginRight='12px';
                const reward=label(p,'','+'+t.stars+' ★',14,'#d0b974');reward.style.width='62px';
                [p,badge,title,status,reward].forEach(target=>{activate(target,()=>selectGroup(g,t));hint(target,condition(t));});
                detail.rows.push({panel:p,data:t,status});
            });
        }
        detail.rows.forEach(r=>{r.panel.style.backgroundColor=r.data===a?'#ffffff0a':'#ffffff00';r.status.text=complete(r.data)?'✓':String(r.data.target);r.status.style.color=complete(r.data)?'#b9d2a8':'#aab8c1';});
    }
    function buildRecent(parent) {
        const section=panel(parent,'CareerRecent','down');section.style.width='100%';section.style.marginTop='12px';
        const history=(saved.recent_unlocks||[]).map(r=>({data:saved.achievements.filter(a=>a.id===r.id)[0],stars:r.stars})).filter(r=>r.data&&r.data.unlocked);
        const fallback=saved.achievements.filter(a=>a.unlocked).slice(0,3).map(a=>({data:a,stars:a.paid_stars}));
        const recent=history.length?history.slice(0,3):fallback;
        label(section,'CareerRecentHeading',history.length?'RECENT UNLOCKS':recent.length?'UNLOCKED ACHIEVEMENTS':'YOUR NEXT MILESTONE',12,'#8c99a4');
        const strip=row(section,'CareerRecentStrip');strip.style.marginTop='5px';
        if(!recent.length) {
            const empty=label(strip,'CareerRecentEmpty','Your first unlock will appear here. Select a goal below to get started.',14,'#aab8c1');empty.style.height='44px';return;
        }
        recent.forEach((r,i)=>{
            const a=r.data,p=panel(strip,'CareerRecent'+i,'right');p.style.width='32%';p.style.marginRight='1%';p.style.padding='8px 10px';p.style.height='58px';p.style.backgroundColor='#ffffff06';
            const icon=picture(p,'',a.icon,24);icon.style.marginRight='10px';icon.style.verticalAlign='center';
            const body=panel(p,'','down');body.style.width='fill-parent-flow(1)';
            const title=label(body,'',a.title,15,'#d9e7d0');
            const status=label(body,'',a.paid?(r.stars>0?'+'+r.stars+' ★ awarded':'Completed'):'Reward pending',12,'#9ba9b2');
            [p,icon,title,status].forEach(target=>{activate(target,()=>{selectFilter(a.category);selectGroup(groups.filter(g=>g.key===a.key)[0],a);});hint(target,condition(a));});
            recentCards.push(p);
        });
    }
    function buildBrowser(parent) {
        const byKey={};saved.achievements.forEach(a=>{a.amount=Number(a.progress)||0;if(!byKey[a.key])byKey[a.key]=[];byKey[a.key].push(a);});
        Object.keys(byKey).forEach(key=>{
            const tiers=byKey[key].sort((a,b)=>a.target-b.target),first=tiers[0];
            groups.push({key,tiers,name:groupNames[key]||first.title,category:first.category,icon:(tiers.filter(t=>t.icon!=='star')[0]||first).icon});
        });
        buildRecent(parent);
        const browser=row(parent,'CareerBrowser');browser.style.height='460px';browser.style.marginTop='14px';
        const left=panel(browser,'CareerGroupColumn','down');left.style.width='49%';left.style.height='100%';left.style.marginRight='3%';
        const top=row(left,'');top.style.marginTop='0px';label(top,'','ACHIEVEMENT GROUPS',12,'#8c99a4');
        const tally=label(top,'CareerGroupCount',groups.length+' groups · '+saved.achievements.length+' milestones',12,'#8c99a4');tally.style.marginLeft='16px';
        const list=panel(left,'LocalAchievements','down');list.style.width='100%';list.style.height='430px';list.style.marginTop='8px';list.style.overflow='squish scroll';list.style.paddingRight='24px';
        groups.forEach(g=>{
            const p=panel(list,'CareerGroup_'+g.key,'right');p.style.width='100%';p.style.height='88px';p.style.padding='10px';p.style.borderBottom='1px solid #ffffff12';p.style.borderLeft='2px solid #ffffff00';
            const icon=picture(p,'CareerGroupIcon_'+g.key,g.icon,30);icon.style.marginRight='14px';icon.style.marginTop='8px';
            const body=panel(p,'','down');body.style.width='fill-parent-flow(1)';
            const line=row(body,'');line.style.marginTop='0px';
            const title=label(line,'CareerGroupTitle_'+g.key,g.name,19);title.AddClass('stratum-regular-condensed');title.style.width='fill-parent-flow(1)';
            const reward=label(line,'CareerGroupReward_'+g.key,'',14,'#d0b974');reward.style.marginLeft='8px';
            const status=label(body,'CareerGroupStatus_'+g.key,'',12,'#9ba9b2');status.style.marginTop='3px';
            const fill=progressBar(body,'');g.panel=p;g.status=status;g.reward=reward;g.fill=fill;
            g.targets=[p,icon,title,reward,status];g.targets.forEach(target=>activate(target,()=>selectGroup(g)));
        });
        const right=panel(browser,'CareerDetails','down');right.style.width='48%';right.style.height='100%';right.style.padding='14px 30px 14px 18px';right.style.backgroundColor='#ffffff05';right.style.overflow='squish scroll';
        const header=row(right,'');header.style.marginTop='0px';const icon=picture(header,'CareerDetailIcon','star',52);icon.style.marginRight='16px';
        const text=panel(header,'','down');text.style.width='fill-parent-flow(1)';
        const category=label(text,'CareerDetailCategory','',12,'#8c99a4');
        const title=label(text,'CareerDetailTitle','',26);title.AddClass('stratum-regular-condensed');title.style.marginTop='3px';
        const tier=label(right,'CareerDetailTier','',18);tier.style.marginTop='16px';
        const description=label(right,'CareerDetailDescription','',15,'#bdc9d2');description.style.width='100%';description.style.marginTop='9px';
        const counts=row(right,'');counts.style.marginTop='12px';
        const amount=label(counts,'CareerDetailProgress','',18);amount.style.width='fill-parent-flow(1)';
        const reward=label(counts,'CareerDetailReward','',18,'#d0b974');
        const fill=progressBar(right,'CareerDetailBar');
        const status=label(right,'CareerDetailStatus','',12);status.style.marginTop='7px';
        const h=label(right,'','MILESTONES',12,'#8c99a4');h.style.marginTop='20px';
        const tiers=panel(right,'CareerDetailTiers','down');tiers.style.width='100%';tiers.style.marginTop='4px';
        detail={icon,title,category,tier,description,amount,reward,fill,status,tiers,rows:[],groupKey:null};
        label(parent,'','Career totals and recent unlocks refresh on launch. Rewards are credited automatically.',12,'#8c99a4').style.marginTop='10px';
    }
    function updateBrowser(values) {
        let completed=0;
        saved.achievements.forEach(a=>{a.amount=(a.key==='wins'||a.key==='rating')?Number(values[a.key])||0:Number(a.progress)||0;if(complete(a))completed++;});
        groups.forEach(g=>{
            const a=nextTier(g),done=g.tiers.filter(complete).length;
            g.status.text=done+' / '+g.tiers.length+' tiers completed'+(done===g.tiers.length?'':' · '+Math.min(a.amount,a.target)+' / '+a.target);
            g.reward.text=done===g.tiers.length?'✓': '+'+a.stars+' ★';setBar(g.fill,a.amount,a.target,done===g.tiers.length);
            g.targets.forEach(target=>hint(target,condition(a)+'\nSelect to see all '+g.tiers.length+' tiers.'));
        });
        renderDetail();return completed;
    }
'''
