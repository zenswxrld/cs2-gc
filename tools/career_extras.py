"""Useful career goals and factual unboxing summary using the client's native ItemImage panel."""
SCRIPT=r'''
    function buildLocalSettings(parent) {
        settingsPane=panel(parent,'CareerSettingsPane','down');settingsPane.style.width='100%';
        heading(settingsPane,'VIEWMODEL');
        label(settingsPane,'','Weapon position and field of view. Apply before returning to a match; uses your native saved client settings.',14,'#aab8c1').style.marginTop='10px';
        const specs=[['viewmodel_fov','FIELD OF VIEW',40,90,60],['viewmodel_offset_x','HORIZONTAL OFFSET',-5,6.25,1],
                     ['viewmodel_offset_y','FORWARD OFFSET',-5,5,1],['viewmodel_offset_z','VERTICAL OFFSET',-5,5,-1]];
        const inputs=[];
        specs.forEach(spec=>{const r=row(settingsPane,'');label(r,'',spec[1]+'  ('+spec[2]+' to '+spec[3]+')',17).style.width='320px';
            const input=$.CreatePanel('TextEntry',r,'Viewmodel_'+spec[0]);input.style.width='100px';input.style.height='34px';
            const value=Number(GameInterfaceAPI.GetSettingString(spec[0]));input.text=String(Number.isFinite(value)&&value>=spec[2]&&value<=spec[3]?value:spec[4]);
            inputs.push(input);});
        const status=label(settingsPane,'ViewmodelStatus','',13,'#aab8c1');status.style.marginTop='12px';
        const actions=row(settingsPane,'');
        button(actions,'ViewmodelApply','APPLY',()=>{
            const values=inputs.map(p=>Number(p.text));
            if(values.some((v,i)=>!inputs[i].text.trim()||!Number.isFinite(v)||v<specs[i][2]||v>specs[i][3])){status.text='Enter a number inside each displayed range.';return;}
            GameInterfaceAPI.ConsoleCommand('viewmodel_presetpos 0');
            specs.forEach((spec,i)=>GameInterfaceAPI.ConsoleCommand(spec[0]+' '+values[i]));
            status.text='Applied. Inspect the position in a match; you can return here to adjust it.';
        });
        button(actions,'ViewmodelReset','DEFAULT VALUES',()=>inputs.forEach((p,i)=>p.text=String(specs[i][4])));
        heading(settingsPane,'BOT CHAT REACTIONS');
        label(settingsPane,'','Short, delayed reactions to kills, rounds and bomb events. Global and per-bot cooldowns limit chatter.',14,'#aab8c1').style.marginTop='10px';
        const chatter=row(settingsPane,'');
        ['off','less','normal','more'].forEach(mode=>button(chatter,'BotChat_'+mode,mode.toUpperCase(),()=>{
            GameInterfaceAPI.ConsoleCommand('css_bot_chat '+mode);status.text='Bot chat request sent. Change this while in a local bot match; the choice is saved.';
        }));
    }
    const goalSlots=[];
    function buildClosest(parent) {
        const h=label(parent,'CareerClosestHeading','ALMOST THERE',18,'#cdd4da');h.AddClass('stratum-regular-condensed');h.style.marginTop='18px';
        const r=row(parent,'CareerClosest');
        for(let i=0;i<3;i++) {
            const p=panel(r,'CareerClosest'+i,'down');p.style.width='32%';p.style.marginRight='1%';p.style.padding='10px 12px';p.style.height='76px';p.style.backgroundColor='#ffffff06';
            const title=label(p,'CareerClosestTitle'+i,'',17);title.AddClass('stratum-regular-condensed');
            const text=label(p,'CareerClosestProgress'+i,'',12,'#aab8c1');text.style.marginTop='5px';
            const fill=progressBar(p,'');goalSlots.push({panel:p,title,text,fill});
        }
        const rewards=saved.collectibles||{matches:0,paid:0};
        label(parent,'','COLLECTIBLE MILESTONES',18,'#cdd4da').style.marginTop='16px';
        const cabinet=row(parent,'CareerCollectibleMilestones');
        [['PIN',10],['COIN',50],['TROPHY',100]].forEach((entry,i)=>{
            const p=panel(cabinet,'CollectibleMilestone'+i,'down');p.style.width='32%';p.style.marginRight='1%';p.style.padding='10px';p.style.backgroundColor='#ffffff06';
            label(p,'',entry[0]+' · '+((rewards.paid&(1<<i))?'AWARDED':Math.min(rewards.matches,entry[1])+' / '+entry[1]+' MATCHES'),14,'#d0b974');
            hint(p,'Complete '+entry[1]+' local matches to earn one permanent '+entry[0].toLowerCase()+'. The local GC awards it once, separately from care-package choices and star rewards. Uses an available collectible from this build; it does not record an official tournament result.');
        });
    }
    function updateClosest() {
        const upcoming=groups.map(g=>({group:g,data:nextTier(g)})).filter(r=>!complete(r.data));
        upcoming.sort((a,b)=>b.data.amount/b.data.target-a.data.amount/a.data.target);
        const heading=$.GetContextPanel().FindChildInLayoutFile('CareerClosestHeading');
        if(heading)heading.text=upcoming.length?(upcoming[0].data.amount>0?'ALMOST THERE':'NEXT GOALS'):'ALL MILESTONES COMPLETE';
        goalSlots.forEach((slot,i)=>{
            const r=upcoming[i];slot.panel.visible=!!r;if(!r)return;
            const a=r.data;slot.title.text=a.title+'  +'+a.stars+' ★';slot.text.text=Math.min(a.amount,a.target)+' / '+a.target+' · '+r.group.name;
            setBar(slot.fill,a.amount,a.target,false);
            [slot.panel,slot.title,slot.text].forEach(p=>{hint(p,condition(a));activate(p,()=>{selectTab('achievements');selectFilter(a.category);selectGroup(r.group,a);});});
        });
    }
    function buildCompanions(parent) {
        const data=saved.companions||{selected:'0',pets:[],accessories:[],catalogue:[]};
        companionPane=panel(parent,'CareerCompanionsPane','down');companionPane.style.width='100%';
        heading(companionPane,'YOUR CHICKENS');
        const summary=label(companionPane,'CompanionSummary',data.pets.length+' owned · one active follower · permanent ownership',14,'#bdc9d2');summary.style.marginTop='7px';
        const help=label(companionPane,'','Eggs have a 10% chance after a completed match. Hatch in 1–2 more matches, then grow to adulthood. No hunger or expiry.',14,'#8c99a4');help.style.width='100%';help.style.marginTop='8px';
        const status=label(companionPane,'CompanionRequestStatus','Saved collection refreshes on launch. Equipment changes apply through your local GC.',12,'#8c99a4');status.style.marginTop='8px';
        let chosen=data.pets.filter(p=>p.id===data.selected)[0]||data.pets[0]||null;
        function request(id,accessory) {
            if(typeof LoadoutAPI!=='undefined')LoadoutAPI.EquipItemInSlot('noteam',id,id==='0'?'pet':InventoryAPI.GetDefaultSlot(id));
            const local=id==='0'?0:Number(id)-1000000000000,code=accessory===4294967295?31:accessory===0?0:accessory-55000+1;
            if(local>=0&&local<68719476736&&typeof TournamentsAPI!=='undefined')TournamentsAPI.SetTournamentFavorite(4400000000000000+local*32+code,true);
            $.Msg('CS2GC_PET_EQUIP '+id+' '+accessory);data.selected=id;
            status.text='Equipment selection sent. Your local GC validates ownership before applying it.';
        }
        const body=row(companionPane,'CompanionBody');body.style.height='490px';body.style.marginTop='18px';
        const list=panel(body,'CompanionList','down');list.style.width='54%';list.style.marginRight='3%';list.style.height='100%';list.style.overflow='squish scroll';list.style.paddingRight='24px';
        const right=panel(body,'CompanionAccessories','down');right.style.width='43%';right.style.height='100%';right.style.overflow='squish scroll';right.style.paddingRight='24px';
        const title=label(right,'CompanionSelected','',20);title.AddClass('stratum-regular-condensed');
        const progress=label(right,'CompanionGrowth','',14,'#aab8c1');progress.style.marginTop='8px';progress.style.width='100%';
        const accessoryList=panel(right,'CompanionAccessoryList','down');accessoryList.style.width='100%';accessoryList.style.marginTop='12px';
        function drawAccessories() {
            title.text=chosen?chosen.name+' · '+chosen.stage_name:'No chicken selected';
            progress.text=chosen?(chosen.stage===0?'Hatches in '+Math.max(0,chosen.hatch_at-chosen.age)+' completed match(es).':'Appearance seed '+chosen.seed+' · '+(chosen.stage<3?'Grows after another completed match.':'Fully grown.')):'Collect an egg from completed matches. Accessories come from the Chicken Cosmetics Armory collection.';
            accessoryList.RemoveAndDeleteChildren();
            if(!chosen)return;
            const remove=button(accessoryList,'CompanionRemoveHat','REMOVE ACCESSORY',()=>{request(chosen.id,0);chosen.accessory=0;drawAccessories();});remove.panel.style.width='100%';
            (data.catalogue||[]).forEach(a=>{
                const owned=data.accessories.includes(a.definition),p=panel(accessoryList,'CompanionAccessory'+a.definition,'right');
                p.style.width='100%';p.style.height='49px';p.style.marginTop='4px';p.style.padding='5px 8px';p.style.backgroundColor=chosen.accessory===a.definition?'#ffffff12':'#ffffff05';p.style.opacity=owned?'1':'.4';
                const image=$.CreatePanel('Image',p,'');image.SetImage('file://{images}/econ/cs2gc_chicken/'+a.id+'.png');image.style.width='36px';image.style.height='36px';image.style.marginRight='10px';
                const text=label(p,'',a.name+(owned?'':' · LOCKED'),16);text.style.verticalAlign='center';
                [p,image,text].forEach(t=>{hint(t,owned?'Equip '+a.name+' to this chicken. The accessory stays owned when you swap it.':'Obtain this accessory from the Chicken Cosmetics collection in the Armory.');activate(t,()=>{if(!owned)return;request(chosen.id,a.definition);chosen.accessory=a.definition;drawAccessories();});});
            });
        }
        if(!data.pets.length) {const empty=label(list,'CompanionEmpty','Your eggs and chickens will appear here. Each is a separate native inventory item, so you can collect multiple breeds and appearances.',17,'#aab8c1');empty.style.width='100%';empty.style.marginTop='12px';}
        data.pets.forEach((pet,i)=>{
            const p=panel(list,'CompanionPet'+i,'right');p.style.width='100%';p.style.padding='10px';p.style.height='92px';p.style.marginBottom='7px';p.style.backgroundColor='#ffffff07';
            const image=$.CreatePanel('ItemImage',p,'');image.itemid=pet.id;image.style.width='94px';image.style.height='66px';image.style.marginRight='12px';
            const block=panel(p,'','down');block.style.width='fill-parent-flow(1)';
            const name=label(block,'',pet.stage===0?'Chicken Egg':pet.name+' · '+pet.stage_name,20);name.AddClass('stratum-regular-condensed');
            const desc=label(block,'','Seed '+pet.seed+(pet.stage===0?' · '+Math.max(0,pet.hatch_at-pet.age)+' matches to hatch':''),12,'#aab8c1');desc.style.marginTop='6px';
            const selected=label(block,'',pet.id===data.selected?'ACTIVE':'SELECT & EQUIP',12,'#d0b974');selected.style.marginTop='4px';
            [p,image,name,desc,selected].forEach(t=>{hint(t,'Permanent '+pet.name+' companion. Select this individual chicken to equip it or change its accessory. Eggs stay in your inventory until they hatch.');activate(t,()=>{chosen=pet;request(pet.id,4294967295);drawAccessories();selected.text='SELECTION SENT';});});
        });
        button(companionPane,'CompanionDisable','UNEQUIP FOLLOWER',()=>request('0',4294967295));drawAccessories();
    }
    const rarityNames=['Unspecified','Consumer','Industrial','Mil-Spec','Restricted','Classified','Covert','Contraband','Gold'];
    const rarityColors=['#a7b1b9','#b0c3d9','#5e98d9','#4b69ff','#8847ff','#d32ce6','#eb4b4b','#e4ae39','#d7bc68'];
    function pullView(r) {
        let id=null,name='Item '+r.definition;
        if(typeof InventoryAPI!=='undefined') {
            if(typeof InventoryAPI.GetItemDefinitionIndex==='function'&&Number(InventoryAPI.GetItemDefinitionIndex(r.id))===r.definition)id=r.id;
            else if(typeof InventoryAPI.GetFauxItemIDFromDefAndPaintIndex==='function')id=InventoryAPI.GetFauxItemIDFromDefAndPaintIndex(r.definition,r.paint);
            if(id&&typeof InventoryAPI.GetItemName==='function')name=InventoryAPI.GetItemName(id)||name;
        }
        if(!id||id!==r.id) {
            if(r.sticker)name='Sticker #'+r.sticker;else if(r.music)name='Music kit #'+r.music;else if(r.charm)name='Charm #'+r.charm;
        }
        if(r.stattrak&&name.indexOf('StatTrak')<0)name='StatTrak™ '+name;
        return {id,name,color:rarityColors[r.gold?8:r.rarity]||rarityColors[0]};
    }
    function pullHint(r,v) {
        return v.name+'\n'+(r.source?'Armory roll':'Container opening')+' · Recorded pull #'+r.sequence+
            (r.paint?'\nFloat: '+Number(r.wear).toFixed(6)+' · Pattern: '+r.seed:'')+'\nKept in your history even if the item is sold.';
    }
    function pullTile(parent,r,id,large) {
        const v=pullView(r),p=panel(parent,id,'right');p.style.width='100%';p.style.height=large?'106px':'62px';p.style.padding='6px 0px';p.style.borderBottom='1px solid #ffffff0f';
        const image=$.CreatePanel('ItemImage',p,id+'Image');if(v.id)image.itemid=v.id;image.style.width=large?'140px':'88px';image.style.height=large?'90px':'48px';image.style.marginRight='10px';
        const body=panel(p,'','down');body.style.width='fill-parent-flow(1)';body.style.verticalAlign='center';
        const title=label(body,id+'Name',v.name,large?18:15,v.color);title.style.width='100%';
        const text=label(body,'',(r.source?'ARMORY':'CONTAINER')+(r.paint?' · '+Number(r.wear).toFixed(4):''),11,'#8c99a4');text.style.marginTop='5px';
        [p,image,title,text].forEach(t=>hint(t,pullHint(r,v)));return p;
    }
    function buildUnboxing(parent) {
        const data=saved.openings||{available:true,total:0,containers:0,armory:0,stattrak:0,rarities:[0,0,0,0,0,0,0,0,0],recent:[],best:[]};
        const side=panel(parent,'CareerUnboxing','down');side.style.width='29%';side.style.marginLeft='2%';side.style.height='100%';side.style.padding='22px';side.style.backgroundColor='#171e25f2';
        label(side,'','UNBOXING RECORD',27).AddClass('stratum-regular-condensed');
        label(side,'OpeningTotal',data.total+' recorded openings',16,'#bdc9d2').style.marginTop='6px';
        const counts=row(side,'OpeningCounters');counts.style.marginTop='14px';
        [['GOLDS',data.rarities[8]||0],['REDS',data.rarities[6]||0],['STATTRAK',data.stattrak]].forEach(pair=>{
            const box=panel(counts,'','down');box.style.width='33%';box.style.padding='8px';box.style.backgroundColor='#ffffff05';
            label(box,'',pair[0],11,'#8c99a4');label(box,'',String(pair[1]),25,'#d0b974');
        });
        const breakdown=panel(side,'OpeningRarities','down');breakdown.style.width='100%';breakdown.style.marginTop='14px';
        const bar=panel(breakdown,'','right');bar.style.width='100%';bar.style.height='5px';
        if(!data.total)bar.style.backgroundColor='#ffffff15';
        data.rarities.forEach((n,i)=>{if(!n)return;const seg=panel(bar,'','');seg.style.width=(n/data.total*100)+'%';seg.style.height='100%';seg.style.backgroundColor=rarityColors[i];});
        const line=label(breakdown,'OpeningRaritySummary',data.total?data.rarities.map((n,i)=>n?rarityNames[i]+' '+n:'').filter(Boolean).join('   ·   '):'Your rarity breakdown will appear here.',12,'#aab8c1');line.style.width='100%';line.style.marginTop='8px';
        hint(line,'Recorded results only. Gold means a special knife or gloves. Other rarity labels follow the item schema.');
        heading(side,'BEST PULL');
        if(data.best.length)pullTile(side,data.best[0],'OpeningBest',true);
        else {const empty=label(side,'OpeningBestEmpty','Your first opening will start your record.',15,'#aab8c1');empty.style.width='100%';empty.style.height='72px';empty.style.marginTop='12px';}
        const nav=row(side,'OpeningTabs');nav.style.marginTop='14px';nav.style.borderBottom='1px solid #ffffff16';
        const list=panel(side,'OpeningHistory','down');list.style.width='100%';list.style.height='290px';list.style.marginTop='6px';list.style.overflow='squish scroll';list.style.paddingRight='24px';
        let choices=[];
        function choose(mode) {
            list.RemoveAndDeleteChildren();choices.forEach(t=>t.p.caption.style.color=t.key===mode?'#e9f1f6':'#89959e');
            const rows=data[mode]||[];rows.forEach((r,i)=>pullTile(list,r,'Opening_'+mode+'_'+i,false));
            if(!rows.length){const empty=label(list,'OpeningEmpty','No recorded openings yet. Cases, capsules and random Armory pulls will be recorded from this update.',14,'#aab8c1');empty.style.width='100%';empty.style.marginTop='12px';}
        }
        choices.push({key:'recent',p:button(nav,'OpeningRecentTab','RECENT',()=>choose('recent'))});
        choices.push({key:'best',p:button(nav,'OpeningBestTab','TOP 3',()=>choose('best'))});choose('recent');
        const note=label(side,'OpeningNotes',data.available===false?'Saved record unavailable; no results were inferred.':data.containers+' containers · '+data.armory+' Armory rolls\nSaved record refreshes on launch.',12,'#8c99a4');note.style.width='100%';note.style.marginTop='12px';
        hint(note,'Best pulls are ranked by rarity, then StatTrak, then lower float, with newer pulls breaking ties. This is not a market-value estimate. Old inventory items, trade-ups, purchases of unopened cases and match grants are not counted as past unboxings.');
    }
'''
