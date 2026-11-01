"""Build stable form identities separately from National Dex species numbers."""
import concurrent.futures
import csv
import hashlib
import io
import json
from pathlib import Path
import sys

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_national_catalog import ROOT, CACHE, RESOURCES, download

LOCK = json.loads((ROOT / 'scripts/catalog/upstream-lock.json').read_text())
SOURCE = CACHE / LOCK['data']
LANGS = {'english': '9', 'chinese': '12', 'japanese': '11'}

# Used only when the upstream localized form name is absent. These describe
# the recorded form, rather than inventing Pokémon behavior or lore.
WORDS = {
    'alola': ('阿罗拉的样子', 'アローラのすがた'), 'galar': ('伽勒尔的样子', 'ガラルのすがた'),
    'hisui': ('洗翠的样子', 'ヒスイのすがた'), 'paldea': ('帕底亚的样子', 'パルデアのすがた'),
    'mega': ('超级进化', 'メガシンカ'), 'mega-x': ('超级进化 X', 'メガシンカ X'),
    'mega-y': ('超级进化 Y', 'メガシンカ Y'), 'mega-z': ('超级进化 Z', 'メガシンカ Z'),
    'mega-male': ('超级进化·雄性', 'メガシンカ・オス'), 'mega-female': ('超级进化·雌性', 'メガシンカ・メス'),
    'gmax': ('超极巨化', 'キョダイマックス'), 'primal': ('原始回归', 'ゲンシカイキ'),
    'black': ('暗黑', 'ブラック'), 'white': ('焰白', 'ホワイト'),
    'dusk': ('黄昏之鬃', 'たそがれのたてがみ'), 'dawn': ('拂晓之翼', 'あかつきのつばさ'),
    'ice': ('冰', 'こおり'), 'shadow': ('暗影', 'こくば'), 'ultra': ('究极', 'ウルトラ'),
    'male': ('雄性', 'オス'), 'female': ('雌性', 'メス'),
    'attack': ('攻击形态', 'アタックフォルム'), 'defense': ('防御形态', 'ディフェンスフォルム'),
    'speed': ('速度形态', 'スピードフォルム'), 'origin': ('起源形态', 'オリジンフォルム'),
    'therian': ('灵兽形态', 'れいじゅうフォルム'), 'sky': ('天空形态', 'スカイフォルム'),
    'unbound': ('解放形态', 'ときはなたれしすがた'), 'resolute': ('觉悟形态', 'かくごのすがた'),
    'pirouette': ('舞步形态', 'ステップフォルム'), 'blade': ('刀剑形态', 'ブレードフォルム'),
    'school': ('鱼群形态', 'むれたすがた'), 'sunshine': ('晴天形态', 'ポジフォルム'),
    'sunny': ('太阳的样子', 'たいようのすがた'), 'rainy': ('雨水的样子', 'あまみずのすがた'),
    'snowy': ('雪云的样子', 'ゆきぐものすがた'), 'zen': ('达摩模式', 'ダルマモード'),
    'galar-standard': ('伽勒尔·普通模式', 'ガラル・ノーマルモード'),
    'galar-zen': ('伽勒尔·达摩模式', 'ガラル・ダルマモード'),
    'red': ('红色', 'あかいろ'), 'blue': ('蓝色', 'あおいろ'), 'yellow': ('黄色', 'きいろ'),
    'green': ('绿色', 'みどりいろ'), 'orange': ('橙色', 'オレンジいろ'),
    'indigo': ('靛色', 'あいいろ'), 'violet': ('紫色', 'むらさきいろ'),
    'east': ('东海', 'ひがしのうみ'), 'summer': ('夏天的样子', 'なつのすがた'),
    'autumn': ('秋天的样子', 'あきのすがた'), 'winter': ('冬天的样子', 'ふゆのすがた'),
    'heat': ('加热', 'ヒート'), 'wash': ('清洗', 'ウォッシュ'), 'frost': ('结冰', 'フロスト'),
    'fan': ('旋转', 'スピン'), 'mow': ('切割', 'カット'), 'burn': ('火焰卡带', 'ブレイズカセット'),
    'douse': ('水流卡带', 'アクアカセット'), 'chill': ('冰冻卡带', 'フリーズカセット'), 'shock': ('闪电卡带', 'イナズマカセット'),
    'sandy': ('砂土蓑衣', 'すなちのミノ'), 'trash': ('垃圾蓑衣', 'ゴミのミノ'),
    'midnight': ('黑夜的样子', 'まよなかのすがた'), 'dandy': ('绅士造型', 'ジェントルカット'),
    'debutante': ('淑女造型', 'レディカット'), 'diamond': ('菱形造型', 'ダイヤカット'),
    'heart': ('心形造型', 'ハートカット'), 'star': ('星形造型', 'スターカット'),
    'pharaoh': ('国王造型', 'キングダムカット'), 'kabuki': ('歌舞伎造型', 'カブキカット'),
    'la-reine': ('女王造型', 'クイーンカット'), 'matron': ('贵妇造型', 'マダムカット'),
    'small': ('小尺寸', 'ちいさいサイズ'), 'large': ('大尺寸', 'おおきいサイズ'),
    'super': ('特大尺寸', 'とくだいサイズ'), 'pom-pom': ('啪滋啪滋风格', 'ぱちぱちスタイル'),
    'pau': ('呼拉呼拉风格', 'ふらふらスタイル'), 'sensu': ('轻盈轻盈风格', 'まいまいスタイル'),
    'noice': ('解冻头', 'ナイスフェイス'), 'hangry': ('空腹花纹', 'はらぺこもよう'),
    'gulping': ('一口吞的样子', 'うのみのすがた'), 'gorging': ('大口吞的样子', 'まるのみのすがた'),
    'low-key': ('低调的样子', 'ローなすがた'), 'hero': ('全能形态', 'マイティフォルム'),
    'crowned': ('王者形态', 'けんのおう・たてのおう'), 'eternamax': ('无极巨化', 'ムゲンダイマックス'),
    'dada': ('阿爸', 'とうちゃん'), 'bloodmoon': ('赫月', 'アカツキ'),
    'family-of-three': ('三只家庭', '３びきかぞく'), 'three-segment': ('三节形态', 'みつふしフォルム'),
    'artisan': ('高档货', 'タカイモノ'), 'masterpiece': ('高档货', 'タカイモノ'),
    'antique': ('真品', 'しんさくではないすがた'), 'original': ('原始颜色', 'オリジナルカラー'),
    'complete': ('完全体形态', 'パーフェクトフォルム'), '10': ('10%形态', '１０％フォルム'),
    '10-power-construct': ('10%·群聚变形', '１０％・スワームチェンジ'),
    '50-power-construct': ('50%·群聚变形', '５０％・スワームチェンジ'),
    'active': ('活跃模式', 'アクティブモード'), 'eternal': ('永恒之花', 'えいえんのはな'),
    'ash': ('小智版', 'サトシゲッコウガ'), 'battle-bond': ('牵绊变身', 'きずなへんげ'),
    'own-tempo': ('我行我素', 'マイペース'), 'starter': ('搭档', 'あいぼう'),
    'cosplay': ('换装', 'おきがえ'), 'rock-star': ('摇滚巨星', 'ハードロック'),
    'belle': ('贵妇', 'マダム'), 'pop-star': ('偶像', 'アイドル'), 'phd': ('博士', 'ドクター'), 'libre': ('面罩摔角手', 'マスクド'),
    'spiky-eared': ('刺刺耳', 'ギザみみ'), 'original-cap': ('初始帽子', 'オリジナルキャップ'),
    'hoenn-cap': ('丰缘帽子', 'ホウエンキャップ'), 'sinnoh-cap': ('神奥帽子', 'シンオウキャップ'),
    'unova-cap': ('合众帽子', 'イッシュキャップ'), 'kalos-cap': ('卡洛斯帽子', 'カロスキャップ'),
    'alola-cap': ('阿罗拉帽子', 'アローラキャップ'), 'partner-cap': ('就决定是你了之帽', 'キミにきめたキャップ'),
    'world-cap': ('世界帽子', 'ワールドキャップ'), 'totem': ('霸主', 'ぬし'),
    'totem-alola': ('阿罗拉·霸主', 'アローラ・ぬし'), 'busted': ('现形的样子', 'ばれたすがた'),
    'totem-busted': ('霸主·现形', 'ぬし・ばれたすがた'), 'totem-disguised': ('霸主·画皮', 'ぬし・ばけたすがた'),
    'paldea-combat-breed': ('帕底亚·斗战种', 'パルデア・コンバットしゅ'),
    'paldea-blaze-breed': ('帕底亚·火炽种', 'パルデア・ブレイズしゅ'),
    'paldea-aqua-breed': ('帕底亚·水澜种', 'パルデア・ウォーターしゅ'),
    'red-striped': ('红条纹', 'あかすじ'), 'blue-striped': ('蓝条纹', 'あおすじ'), 'white-striped': ('白条纹', 'しろすじ'),
    'blue-plumage': ('蓝羽毛', 'ブルーフェザー'), 'yellow-plumage': ('黄羽毛', 'イエローフェザー'), 'white-plumage': ('白羽毛', 'ホワイトフェザー'),
    'droopy': ('下垂姿势', 'たれたすがた'), 'stretchy': ('平挺姿势', 'のびたすがた'),
    'rapid-strike': ('连击流', 'れんげきのかた'), 'roaming': ('徒步形态', 'とほフォルム'),
    'terastal': ('太晶形态', 'テラスタルフォルム'), 'stellar': ('星晶形态', 'ステラフォルム'),
    'wellspring-mask': ('水井面具', 'いどのめん'), 'hearthflame-mask': ('火灶面具', 'かまどのめん'),
    'cornerstone-mask': ('础石面具', 'いしずえのめん'),
    'limited-build': ('受限形态', 'せいげんけいたい'), 'sprinting-build': ('疾驰形态', 'しっそうけいたい'),
    'swimming-build': ('游泳形态', 'ゆうえいけいたい'), 'gliding-build': ('滑翔形态', 'かっくうけいたい'),
    'low-power-mode': ('低电量模式', 'ローパワーモード'), 'drive-mode': ('行驶模式', 'ドライブモード'),
    'aquatic-mode': ('水上模式', 'フロートモード'), 'glide-mode': ('滑翔模式', 'グライドモード'),
    'unknown': ('未知形态', 'ふめいなすがた'),
}
for key, cn, ja in [('archipelago','群岛','ぐんとう'),('continental','大陆','たいりく'),('elegant','高雅','みやび'),
                    ('fancy','幻彩','ファンシー'),('garden','庭园','ていえん'),('high-plains','荒野','こうや'),
                    ('icy-snow','冰雪','ひょうせつ'),('jungle','热带雨林','ジャングル'),('marine','大海','マリン'),
                    ('meadow','花园','はなぞの'),('modern','摩登','モダン'),('monsoon','骤雨','スコール'),
                    ('ocean','大洋','オーシャン'),('poke-ball','球球','ボール'),('polar','雪国','ゆきぐに'),
                    ('river','江河','たいが'),('sandstorm','沙尘','さじん'),('savanna','热带草原','サバンナ'),
                    ('sun','太阳','たいよう'),('tundra','雪原','せつげん')]:
    WORDS[key] = (cn + '花纹', ja + 'のもよう')
FLAVORS = {'vanilla-cream':('奶香香草','ミルキィバニラ'),'ruby-cream':('奶香红钻','ミルキィルビー'),
           'matcha-cream':('奶香抹茶','ミルキィまっちゃ'),'mint-cream':('奶香薄荷','ミルキィミント'),
           'lemon-cream':('奶香柠檬','ミルキィレモン'),'salted-cream':('奶香海盐','ミルキィソルト'),
           'ruby-swirl':('红钻综合','ルビーミックス'),'caramel-swirl':('焦糖综合','キャラメルミックス'),
           'rainbow-swirl':('三色综合','トリプルミックス')}
SWEETS = {'strawberry-sweet':('草莓糖饰','いちごアメざいく'),'berry-sweet':('树莓糖饰','ベリーアメざいく'),
          'love-sweet':('爱心糖饰','ハートアメざいく'),'star-sweet':('星星糖饰','スターアメざいく'),
          'clover-sweet':('幸运草糖饰','よつばアメざいく'),'flower-sweet':('花朵糖饰','おはなアメざいく'),
          'ribbon-sweet':('蝴蝶结糖饰','リボンアメざいく')}
TYPE_CN = dict(zip('normal fighting flying poison ground rock bug ghost steel fire water grass electric psychic ice dragon dark fairy'.split(),
                   '一般 格斗 飞行 毒 地面 岩石 虫 幽灵 钢 火 水 草 电 超能力 冰 龙 恶 妖精'.split()))
TYPE_JA = dict(zip(TYPE_CN, 'ノーマル かくとう ひこう どく じめん いわ むし ゴースト はがね ほのお みず くさ でんき エスパー こおり ドラゴン あく フェアリー'.split()))
TYPE_CN['unknown'] = '未知'
TYPE_JA['unknown'] = '？？？'
FUSIONS = {'kyurem-white': (643, '焰白酋雷姆'), 'kyurem-black': (644, '暗黑酋雷姆'),
           'necrozma-dusk': (791, '奈克洛兹玛（黄昏之鬃）'), 'necrozma-dawn': (792, '奈克洛兹玛（拂晓之翼）'),
           'calyrex-ice': (896, '蕾冠王（骑白马的样子）'), 'calyrex-shadow': (897, '蕾冠王（骑黑马的样子）')}

def rows(name):
    return list(csv.DictReader((SOURCE / name).open(encoding='utf-8')))

def label(form, language, names):
    translated = names.get((form['id'], LANGS[language]), {})
    if translated.get('form_name'):
        return translated['form_name']
    token = form['form_identifier']
    if language == 'english':
        return token.replace('-', ' ').title() or 'Standard'
    if len(token) == 1 and token.isalpha():
        return token.upper()
    if token in ('exclamation', 'question'):
        return '!' if token == 'exclamation' else '?'
    at = 0 if language == 'chinese' else 1
    if token.endswith('-meteor'):
        return WORDS[token[:-7]][at] + ('流星形态' if at == 0 else '・りゅうせいのすがた')
    if token in TYPE_CN:
        return (TYPE_CN if at == 0 else TYPE_JA)[token] + ('属性' if at == 0 else 'タイプ')
    if token in WORDS:
        return WORDS[token][at]
    for flavor, text in FLAVORS.items():
        if token.startswith(flavor + '-'):
            return text[at] + '・' + SWEETS[token[len(flavor)+1:]][at]
    raise ValueError(('Missing localized form label', form['identifier'], language, token))

def main():
    curated = json.loads((ROOT/'scripts/catalog/form-description-overrides.json').read_text(encoding='utf-8'))['entries']
    species = {p['id']: p for p in json.loads((RESOURCES / 'pokemon-national.json').read_text(encoding='utf-8'))}
    pokemon = {p['id']: p for p in rows('pokemon.csv')}
    names = {(p['pokemon_form_id'], p['local_language_id']): p for p in rows('pokemon_form_names.csv')}
    type_ids = {p['id']: p['identifier'] for p in rows('types.csv')}
    stat_ids = {p['id']: p['identifier'] for p in rows('stats.csv')}
    types, stats = {}, {}
    for p in rows('pokemon_types.csv'): types.setdefault(p['pokemon_id'], []).append((int(p['slot']), type_ids[p['type_id']]))
    for p in rows('pokemon_stats.csv'): stats.setdefault(p['pokemon_id'], []).append({'name': stat_ids[p['stat_id']], 'value': int(p['base_stat'])})
    form_types = {}
    for p in rows('pokemon_form_types.csv'): form_types.setdefault(p['pokemon_form_id'], []).append((int(p['slot']), type_ids[p['type_id']]))
    versions = {p['id']: int(p['generation_id']) for p in rows('version_groups.csv')}
    files = {p['path'] for p in json.loads((CACHE / 'pokemon-tree.json').read_text())['tree'] if p['type'] == 'blob'}
    source_paths = json.loads((ROOT / 'artifacts/forms/sprite-paths.json').read_text())
    forms, metadata = [], {}
    cry_ids = {p['id'] for p in json.loads((RESOURCES/'Cries/cry-sources.json').read_text(encoding='utf-8'))}
    unresolved = []
    for form in rows('pokemon_forms.csv'):
        p = pokemon[form['pokemon_id']]
        sid = int(p['species_id'])
        if sid not in species: continue
        base = species[sid]
        if p['is_default'] == '1' and form['is_default'] == '1':
            metadata[str(sid)] = {'formIdentifier': form['identifier'], 'sourceFormID': int(form['id'])}
            continue
        entry = dict(base)
        entry.update(id=100000 + int(form['id']), speciesID=sid, sourcePokemonID=int(p['id']),
                     sourceFormID=int(form['id']), formIdentifier=form['identifier'], formOrder=int(form['form_order']),
                     generation=versions.get(form['introduced_in_version_group_id'], base['generation']),
                     height=max(0,int(p['height']))/10, weight=max(0,int(p['weight']))/10,
                     types=[x[1] for x in sorted(form_types.get(form['id'], types[p['id']]))], stats=stats[p['id']],
                     cryID=int(p['id']) if int(p['id']) in cry_ids else sid, spriteAsset=f'pokemon-form-{form["id"]}', formCategory='alternate',
                     aliases=[form['identifier']], descriptionSource='Localized summary of pinned form name, species, types and fusion partner')
        token = form['form_identifier']
        entry['heightUnavailable'] = int(p['height']) <= 0
        entry['weightUnavailable'] = int(p['weight']) <= 0
        if token in ['alola','galar','hisui','paldea','galar-standard','galar-zen','paldea-combat-breed','paldea-blaze-breed','paldea-aqua-breed']: entry['formCategory'] = 'regional'
        elif token.startswith('mega'): entry['formCategory'] = 'mega'
        elif token == 'gmax': entry['formCategory'] = 'gigantamax'
        if form['identifier'] in FUSIONS: entry['formCategory'] = 'fusion'
        for region, local in [('alola','阿罗拉'),('galar','伽勒尔'),('hisui','洗翠'),('paldea','帕底亚')]:
            if region in token:
                entry['aliases'].extend([local+base['chineseName'],local+'地区'+base['chineseName']])
        for language in LANGS:
            form_label = label(form, language, names)
            entry[language+'FormName'] = form_label
            full = names.get((form['id'], LANGS[language]), {}).get('pokemon_name')
            entry[language+'Name'] = full or base[language+'Name'] + (' (' if language == 'english' else '（') + form_label + (')' if language == 'english' else '）')
            if language == 'chinese' and form['identifier'] in FUSIONS: entry['chineseName'] = FUSIONS[form['identifier']][1]
            if language == 'english':
                description = f'{form_label} of {base["englishName"]}. Its types are {" and ".join(entry["types"])}.'
            elif language == 'chinese':
                description = f'{base["chineseName"]}的{form_label}。属性为{"、".join(TYPE_CN[t] for t in entry["types"])}。'
            else:
                description = f'{base["japaneseName"]}の{form_label}。{"・".join(TYPE_JA[t] for t in entry["types"])}タイプ。'
            if form['identifier'] in FUSIONS:
                partner = species[FUSIONS[form['identifier']][0]]
                if language == 'english': description = f'A fusion of {base["englishName"]} and {partner["englishName"]}. ' + description
                elif language == 'chinese': description = f'{base["chineseName"]}与{partner["chineseName"]}结合形成的合体形态。' + description
                else: description = f'{base["japaneseName"]}と{partner["japaneseName"]}が合体したすがた。' + description
            entry[language+'Description'] = description
        if form['identifier'] in curated:
            override = curated[form['identifier']]
            assert override['entryID'] == entry['id'], ('Curated form identity changed', form['identifier'])
            for language in LANGS:
                entry[language+'Description'] = override[language+'Description']
            entry['descriptionSource'] = 'Editorial paraphrase of verified official form-specific field notes; see scripts/catalog/form-description-overrides.json'
        source = source_paths.get(form['id'])
        if source:
            entry['spriteSourcePath'] = 'sprites/pokemon/' + source
        else:
            entry['spriteAsset'] = f'pokemon-{sid:03d}'
            entry['spriteReferenceOnly'] = True
            unresolved.append(form['identifier'])
            for language, note in [('english','The illustration currently shows the base species; a separate pixel sprite for this form is not available. '),('chinese','本形态暂无独立像素图，图示暂为基础形态。'),('japanese','このすがたの専用スプライトは未収録のため、基本のすがたを参考表示しています。')]:
                entry[language+'Description'] = note + entry[language+'Description']
        if form['identifier'].startswith(('mothim-', 'scatterbug-', 'spewpa-')):
            entry['visualAliasOf'] = sid
            entry['spriteReferenceOnly'] = False
            # These records encode the future evolution's pattern; the current
            # Pokémon itself has the same appearance, not a missing illustration.
            for language in LANGS:
                entry[language+'Description'] = entry[language+'Description'].split('. ',1)[-1] if language=='english' else entry[language+'Description'].split('。',1)[-1]
        forms.append(entry)
    def asset(entry):
        relative = entry.get('spriteSourcePath')
        if not relative: return
        original = download(f'https://raw.githubusercontent.com/PokeAPI/sprites/{LOCK["sprites"]}/{relative}', CACHE / 'forms-sprites' / relative)
        with Image.open(io.BytesIO(original)) as source:
            image = source.convert('RGBA')
            if image.size != (96,96):
                ratio = min(92/image.width, 92/image.height)
                image = image.resize((round(image.width*ratio),round(image.height*ratio)), Image.Resampling.NEAREST)
                canvas = Image.new('RGBA',(96,96)); canvas.alpha_composite(image,((96-image.width)//2,(96-image.height)//2)); image = canvas
            destination = RESOURCES / 'PokemonSprites.xcassets' / (entry['spriteAsset'] + '.imageset')
            destination.mkdir(exist_ok=True)
            image.save(destination / 'sprite.png')
            (destination/'Contents.json').write_text(json.dumps({'images':[{'filename':'sprite.png','idiom':'universal'}],'info':{'author':'xcode','version':1}},indent=2)+'\n',encoding='utf-8',newline='\n')
        entry['spriteSourceSHA256'] = hashlib.sha256(original).hexdigest()
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
        for index, _ in enumerate(pool.map(asset, forms),1):
            if index % 100 == 0: print(f'Form sprites {index}/{len(forms)}',flush=True)
    (RESOURCES/'pokemon-forms.json').write_text(json.dumps(forms,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    (RESOURCES/'base-form-metadata.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    report={'species':len(species),'additionalForms':len(forms),'entries':len(species)+len(forms),'sourceRevisions':LOCK,'unresolvedSpriteForms':[p['formIdentifier'] for p in forms if p.get('spriteReferenceOnly')]}
    (RESOURCES/'forms-manifest.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(report),flush=True)

if __name__ == '__main__': main()
