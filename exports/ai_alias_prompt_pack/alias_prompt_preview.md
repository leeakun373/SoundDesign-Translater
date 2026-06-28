# AI Alias Prompt Preview

This file is a local input preview. No AI service was called.

## Required output format

```csv
raw,canonical,slot,lang,priority,rule_type,review_status,ambiguity,tags,source,note
```

Output constraints:

- `review_status` must be `review`.
- `source` must be `ai_candidate`.
- `priority` must be `0`.
- Never output `keep`.
- Do not output free-translation sentences or metadata descriptions.
- Do not overwrite `canonical_tokens.csv`.

## Item 1: Impact

- canonical: `Impact`
- slot: `action`
- candidate_type: `token`
- record_count: `1552`
- AI instruction: Generate conservative Chinese aliases for a sound-design FXName token. Do not translate freely. Return only aliases that a Chinese sound designer would actually type.
- examples:
  - {"fx_name":"Plunger Water Impact Hard","description":"Force Cup. Wet, tight, resonant impacts with splashing at the end. Mono, Sanken Co100K high frequency response.","category":"CREATURES/SOURCE","cat_id":"CREASrce"}
  - {"fx_name":"Plunger Water Impact Hard","description":"Force Cup. Wet, tight, resonant impacts with splashing at the end. Mono, Sanken Co100K high frequency response.","category":"CREATURES/SOURCE","cat_id":"CREASrce"}
  - {"fx_name":"Plunger Water Impact Hard","description":"Force Cup. Wet, tight, resonant impacts with splashing at the end. Mono, Sanken Co100K high frequency response.","category":"CREATURES/SOURCE","cat_id":"CREASrce"}

## Item 2: Car

- canonical: `Car`
- slot: `object`
- candidate_type: `token`
- record_count: `1470`
- AI instruction: Generate conservative Chinese aliases for a sound-design FXName token. Do not translate freely. Return only aliases that a Chinese sound designer would actually type.
- examples:
  - {"fx_name":"Countryside Cow Barn Night Occasional Traffic Belgium","description":"VRIJSTRAAT - Countryside near cow barn with small fountain at night. Water splatter throughout. Occasional cow mooing, noises inside barn a…","category":"AMBIENCE/FARM","cat_id":"AMBFarm"}
  - {"fx_name":"Countryside Farming Machines England","description":"STELLING MINNIS - Countryside with farming machines. Crickets, bird twitter and semi-distant machine rattle throughout. Occasional car driv…","category":"AMBIENCE/FARM","cat_id":"AMBFarm"}
  - {"fx_name":"Small Town Empty Market Hall Hum France","description":"FOIX - Empty market hall with ventilation hum. Distant bird chirping throughout. Car drive bys occasionally. No pedestrian activity or voic…","category":"AMBIENCE/MARKET","cat_id":"AMBMrkt"}

## Item 3: Friction

- canonical: `Friction`
- slot: `action`
- candidate_type: `token`
- record_count: `231`
- AI instruction: Generate conservative Chinese aliases for a sound-design FXName token. Do not translate freely. Return only aliases that a Chinese sound designer would actually type.
- examples:
  - {"fx_name":"Balloon Friction Rub Very High","description":"Scrape. Tonal, slightly raspy scraping and moaning. Mono, Sanken Co100K high frequency response.","category":"CREATURES/SOURCE","cat_id":"CREASrce"}
  - {"fx_name":"Balloon Friction Rub Very High","description":"Scrape. Tonal, slightly raspy scraping and moaning. Mono, Sanken Co100K high frequency response.","category":"CREATURES/SOURCE","cat_id":"CREASrce"}
  - {"fx_name":"Balloon Friction Rub Very High","description":"Scrape. Tonal, slightly raspy scraping and moaning. Mono, Sanken Co100K high frequency response.","category":"CREATURES/SOURCE","cat_id":"CREASrce"}

## Item 4: Gun

- canonical: `Gun`
- slot: `object`
- candidate_type: `token`
- record_count: `2376`
- AI instruction: Generate conservative Chinese aliases for a sound-design FXName token. Do not translate freely. Return only aliases that a Chinese sound designer would actually type.
- examples:
  - {"fx_name":"Rip Tear Tape Gun Cardboard Box Fast","description":"Scratch. Aggressive, slightly tonal, resonant screeching and moaning with varying pitch. Mono, Sanken Co100K high frequency response.","category":"CREATURES/SOURCE","cat_id":"CREASrce"}
  - {"fx_name":"Rip Tear Tape Gun Cardboard Box Fast","description":"Scratch. Aggressive, slightly tonal, resonant screeching and moaning with varying pitch. Mono, Sanken Co100K high frequency response.","category":"CREATURES/SOURCE","cat_id":"CREASrce"}
  - {"fx_name":"Rip Tear Tape Gun Cardboard Box Fast","description":"Scratch. Aggressive, slightly tonal, resonant screeching and moaning with varying pitch. Mono, Sanken Co100K high frequency response.","category":"CREATURES/SOURCE","cat_id":"CREASrce"}

## Item 5: Hit

- canonical: `Hit`
- slot: `action`
- candidate_type: `token`
- record_count: `1418`
- AI instruction: Generate conservative Chinese aliases for a sound-design FXName token. Do not translate freely. Return only aliases that a Chinese sound designer would actually type.
- examples:
  - {"fx_name":"Pre Dawn Drips Heavy","description":"Pre dawn in the Amazon jungle as heavy drops of water fall from the canopy and hit broad leafed plants. Chirping insects and birds calling…","category":"AMBIENCE/TROPICAL","cat_id":"AMBTrop"}
  - {"fx_name":"Pre Dawn Drips","description":"Pre dawn in the Amazon jungle as light drops of water fall from the canopy and hit broad leafed plants. Chirping insects and birds calling…","category":"AMBIENCE/TROPICAL","cat_id":"AMBTrop"}
  - {"fx_name":"Dawn Howler Monkeys Distant","description":"Distant howler monkeys eerily vocalizing, birds begin at dawn in Amazon jungle. Water drops hit broad leafs. Chirping, flying insects throu…","category":"AMBIENCE/TROPICAL","cat_id":"AMBTrop"}

## Item 6: Squeak

- canonical: `Squeak`
- slot: `action`
- candidate_type: `token`
- record_count: `172`
- AI instruction: Generate conservative Chinese aliases for a sound-design FXName token. Do not translate freely. Return only aliases that a Chinese sound designer would actually type.
- examples:
  - {"fx_name":"Water Bath Toy Squeeze Squeak","description":"Sizzle. Wet, resonant, airy, raspy, slightly tonal squeezing, screeching and hissing. Mono, Sanken Co100K high frequency response.","category":"CREATURES/SOURCE","cat_id":"CREASrce"}
  - {"fx_name":"Water Bath Toy Squeeze Squeak","description":"Sizzle. Wet, resonant, airy, raspy, slightly tonal squeezing, screeching and hissing. Mono, Sanken Co100K high frequency response.","category":"CREATURES/SOURCE","cat_id":"CREASrce"}
  - {"fx_name":"Water Bath Toy Squeeze Squeak","description":"Sizzle. Wet, resonant, airy, raspy, slightly tonal squeezing, screeching and hissing. Mono, Sanken Co100K high frequency response.","category":"CREATURES/SOURCE","cat_id":"CREASrce"}

## Item 7: Whoosh

- canonical: `Whoosh`
- slot: `action`
- candidate_type: `token`
- record_count: `1564`
- AI instruction: Generate conservative Chinese aliases for a sound-design FXName token. Do not translate freely. Return only aliases that a Chinese sound designer would actually type.
- examples:
  - {"fx_name":"Whoosh Modulation","description":"Rapid motion with whoosh-like modulation.","category":"DESIGNED/MISC","cat_id":"DSGNMisc"}
  - {"fx_name":"Soft Whoosh Filter Movement","description":"Extended motion noise with a gentle whoosh and filter modulation.","category":"DESIGNED/SYNTHETIC","cat_id":"DSGNSynth"}
  - {"fx_name":"Soft Whoosh Filter Movement","description":"Extended motion noise with a gentle whoosh and filter modulation.","category":"DESIGNED/SYNTHETIC","cat_id":"DSGNSynth"}

## Item 8: Gun Shot

- canonical: `Gun Shot`
- slot: `action`
- candidate_type: `phrase`
- record_count: `183`
- AI instruction: Generate conservative Chinese aliases for a sound-design FXName token. Do not translate freely. Return only aliases that a Chinese sound designer would actually type.
- examples:
  - {"fx_name":"16 Pounder 15m","description":"Antique artillery, historic cannon, cal 27mm. MS shotgun microphone positioned 15m away from the cannon.","category":"GUNS/CANNON","cat_id":"GUNCano"}
  - {"fx_name":"16 Pounder 15m","description":"Antique artillery, historic cannon, cal 27mm. MS shotgun microphone positioned 15m away from the cannon.","category":"GUNS/CANNON","cat_id":"GUNCano"}
  - {"fx_name":"16 Pounder 15m","description":"Antique artillery, historic cannon, cal 27mm. MS shotgun microphone positioned 15m away from the cannon.","category":"GUNS/CANNON","cat_id":"GUNCano"}

## Item 9: Projectile Gun Shot

- canonical: `Projectile Gun Shot`
- slot: `action`
- candidate_type: `phrase`
- record_count: `176`
- AI instruction: Generate conservative Chinese aliases for a sound-design FXName token. Do not translate freely. Return only aliases that a Chinese sound designer would actually type.
- examples:
  - {"fx_name":"16 Pounder 15m","description":"Antique artillery, historic cannon, cal 27mm. MS shotgun microphone positioned 15m away from the cannon.","category":"GUNS/CANNON","cat_id":"GUNCano"}
  - {"fx_name":"16 Pounder 15m","description":"Antique artillery, historic cannon, cal 27mm. MS shotgun microphone positioned 15m away from the cannon.","category":"GUNS/CANNON","cat_id":"GUNCano"}
  - {"fx_name":"16 Pounder 15m","description":"Antique artillery, historic cannon, cal 27mm. MS shotgun microphone positioned 15m away from the cannon.","category":"GUNS/CANNON","cat_id":"GUNCano"}

## Item 10: Cannon

- canonical: `Cannon`
- slot: `object`
- candidate_type: `token`
- record_count: `1257`
- AI instruction: Generate conservative Chinese aliases for a sound-design FXName token. Do not translate freely. Return only aliases that a Chinese sound designer would actually type.
- examples:
  - {"fx_name":"Cannon Shot","description":"Extended explosion noise reminiscent of a cannon blast.","category":"EXPLOSIONS/DESIGNED","cat_id":"EXPLDsgn"}
  - {"fx_name":"Cannon Shot","description":"Extended explosion noise reminiscent of a cannon blast.","category":"EXPLOSIONS/DESIGNED","cat_id":"EXPLDsgn"}
  - {"fx_name":"Cannon Shot","description":"Brief explosion noise reminiscent of a cannon blast.","category":"EXPLOSIONS/DESIGNED","cat_id":"EXPLDsgn"}

## Item 11: Shot

- canonical: `Shot`
- slot: `action`
- candidate_type: `token`
- record_count: `1360`
- AI instruction: Generate conservative Chinese aliases for a sound-design FXName token. Do not translate freely. Return only aliases that a Chinese sound designer would actually type.
- examples:
  - {"fx_name":"Saw Wave White Noise Dual Delay Shot","description":"Sharp accent characterised by a saw wave, white noise, and dual delay shot.","category":"DESIGNED/SYNTHETIC","cat_id":"DSGNSynth"}
  - {"fx_name":"Saw Wave White Noise Dual Delay Shot","description":"Sharp accent characterised by a saw wave, white noise, and dual delay shot.","category":"DESIGNED/SYNTHETIC","cat_id":"DSGNSynth"}
  - {"fx_name":"Saw Wave White Noise Dual Delay Shot","description":"Sharp accent characterised by a saw wave, white noise, and dual delay shot.","category":"DESIGNED/SYNTHETIC","cat_id":"DSGNSynth"}

## Item 12: Hard Hit

- canonical: `Hard Hit`
- slot: `action`
- candidate_type: `phrase`
- record_count: `161`
- AI instruction: Generate conservative Chinese aliases for a sound-design FXName token. Do not translate freely. Return only aliases that a Chinese sound designer would actually type.
- examples:
  - {"fx_name":"Ground Impact","description":"PROCESSED RUPTURE Hard hit, with rumbling and crumbling.","category":"DESIGNED/MISC","cat_id":"DSGNMisc"}
  - {"fx_name":"Head","description":"PROCESSED RUPTURE Distorted and hard hit, with cracking and shaking.","category":"DESIGNED/MISC","cat_id":"DSGNMisc"}
  - {"fx_name":"Ice Cream","description":"PROCESSED RUPTURE Hard hit, with loud shattering and breaking.","category":"DESIGNED/DISTORTION","cat_id":"DSGNDist"}

## Item 13: Scrape

- canonical: `Scrape`
- slot: `action`
- candidate_type: `token`
- record_count: `699`
- AI instruction: Generate conservative Chinese aliases for a sound-design FXName token. Do not translate freely. Return only aliases that a Chinese sound designer would actually type.
- examples:
  - {"fx_name":"Balloon Friction Rub Very High","description":"Scrape. Tonal, slightly raspy scraping and moaning. Mono, Sanken Co100K high frequency response.","category":"CREATURES/SOURCE","cat_id":"CREASrce"}
  - {"fx_name":"Cardboard Box Scrape Knife Circle","description":"Scratch, Rub. Aggressive, raspy, resonant scraping with varying movement. Mono, Sanken Co100K high frequency response.","category":"CREATURES/SOURCE","cat_id":"CREASrce"}
  - {"fx_name":"Cardboard Box Scrape Knife Circle","description":"Scratch, Rub. Aggressive, raspy, resonant scraping with varying movement. Mono, Sanken Co100K high frequency response.","category":"CREATURES/SOURCE","cat_id":"CREASrce"}

## Item 14: Break

- canonical: `Break`
- slot: `action`
- candidate_type: `token`
- record_count: `139`
- AI instruction: Generate conservative Chinese aliases for a sound-design FXName token. Do not translate freely. Return only aliases that a Chinese sound designer would actually type.
- examples:
  - {"fx_name":"Slammed Break Up","description":"PROCESSED FLY BY Deep growling, similar to thunderstorm rumbling.","category":"SWOOSHES/WHOOSH","cat_id":"WHSH"}
  - {"fx_name":"Slammed Break Up","description":"PROCESSED FLY BY Deep growling, similar to thunderstorm rumbling.","category":"SWOOSHES/WHOOSH","cat_id":"WHSH"}
  - {"fx_name":"Slammed Break Up","description":"PROCESSED FLY BY Deep growling, similar to thunderstorm rumbling.","category":"SWOOSHES/WHOOSH","cat_id":"WHSH"}

## Item 15: Chain

- canonical: `Chain`
- slot: `object`
- candidate_type: `token`
- record_count: `190`
- AI instruction: Generate conservative Chinese aliases for a sound-design FXName token. Do not translate freely. Return only aliases that a Chinese sound designer would actually type.
- examples:
  - {"fx_name":"Metal Chain Delay Formant Shift","description":"Gleaming effect characterised by a metal chain, delay, and formant shift.","category":"DESIGNED/MISC","cat_id":"DSGNMisc"}
  - {"fx_name":"Metal Chain Delay Formant Shift","description":"Gleaming effect characterised by a metal chain, delay, and formant shift.","category":"DESIGNED/MISC","cat_id":"DSGNMisc"}
  - {"fx_name":"Metal Chain Delay Formant Shift","description":"Gleaming effect characterised by a metal chain, delay, and formant shift.","category":"DESIGNED/MISC","cat_id":"DSGNMisc"}

## Item 16: Crack

- canonical: `Crack`
- slot: `action`
- candidate_type: `token`
- record_count: `114`
- AI instruction: Generate conservative Chinese aliases for a sound-design FXName token. Do not translate freely. Return only aliases that a Chinese sound designer would actually type.
- examples:
  - {"fx_name":"Tight Crack","description":"Brief explosion noise reminiscent of a sharp crack.","category":"EXPLOSIONS/REAL","cat_id":"EXPLReal"}
  - {"fx_name":"Tight Crack","description":"Brief explosion noise reminiscent of a sharp crack.","category":"EXPLOSIONS/REAL","cat_id":"EXPLReal"}
  - {"fx_name":"Tight Crack","description":"Brief explosion noise reminiscent of a sharp crack.","category":"EXPLOSIONS/REAL","cat_id":"EXPLReal"}

## Item 17: Creature

- canonical: `Creature`
- slot: `object`
- candidate_type: `token`
- record_count: `129`
- AI instruction: Generate conservative Chinese aliases for a sound-design FXName token. Do not translate freely. Return only aliases that a Chinese sound designer would actually type.
- examples:
  - {"fx_name":"Behemoth Alerted","description":"Extraterrestrial, Creature, Monster. Deep, threatening growling with harsh, tonal chirping.","category":"CREATURES/MISC","cat_id":"CREAMisc"}
  - {"fx_name":"Behemoth Attack","description":"Extraterrestrial, Creature, Monster. Deep, aggressive growling with short buildup and impact.","category":"CREATURES/MISC","cat_id":"CREAMisc"}
  - {"fx_name":"Behemoth Death","description":"Extraterrestrial, Creature, Monster. Long, deep, agonizing roaring with painful exhaling at the end.","category":"CREATURES/MISC","cat_id":"CREAMisc"}

## Item 18: Door

- canonical: `Door`
- slot: `object`
- candidate_type: `token`
- record_count: `483`
- AI instruction: Generate conservative Chinese aliases for a sound-design FXName token. Do not translate freely. Return only aliases that a Chinese sound designer would actually type.
- examples:
  - {"fx_name":"Mountain Village Small Square Fountain Spain","description":"OS DE CIVÌS - Mountain square with water fountain. Water splatter throughout. Car door close at times.","category":"AMBIENCE/RURAL","cat_id":"AMBRurl"}
  - {"fx_name":"Make A Rule","description":"SYNTHETIC HIT HIGH Distorted bangs, resembling hard hits on a wooden door.","category":"DESIGNED/DISTORTION","cat_id":"DSGNDist"}
  - {"fx_name":"Solid Blast","description":"SYNTHETIC HIT HIGH Vibrating rattle, like quick shaking of an unstable door.","category":"DESIGNED/MISC","cat_id":"DSGNMisc"}

## Item 19: Drop

- canonical: `Drop`
- slot: `action`
- candidate_type: `token`
- record_count: `248`
- AI instruction: Generate conservative Chinese aliases for a sound-design FXName token. Do not translate freely. Return only aliases that a Chinese sound designer would actually type.
- examples:
  - {"fx_name":"Drop it Like Its Hot","description":"SYNTHETIC SCREECH LONG Intense shot of a buzz, with screech at the end.","category":"DESIGNED/TONAL","cat_id":"DSGNTonl"}
  - {"fx_name":"Metal Chain Drop High Ringing","description":"Metallic chain being dropped with tonal ring out.","category":"GUNS/CANNON","cat_id":"CHAINMvmt"}
  - {"fx_name":"Metal Chain Drop High Ringing","description":"Metallic chain being dropped with tonal ring out.","category":"GUNS/CANNON","cat_id":"CHAINMvmt"}

## Item 20: Engine

- canonical: `Engine`
- slot: `object`
- candidate_type: `token`
- record_count: `338`
- AI instruction: Generate conservative Chinese aliases for a sound-design FXName token. Do not translate freely. Return only aliases that a Chinese sound designer would actually type.
- examples:
  - {"fx_name":"Old Town Backyard Calm Belgium","description":"BRUGES - Calm old town backyard. Minimal semi-distant pedestrian activity and voices throughout. Occasional drive by. Dog bark and kids run…","category":"AMBIENCE/RURAL","cat_id":"AMBRurl"}
  - {"fx_name":"Small Town Main Street Traffic Truck Noise France","description":"VENDÔME - Busy small town main street. Truck engine and moderate traffic throughout. Truck signal beep and pneumatics occasionally. Pedestr…","category":"AMBIENCE/RURAL","cat_id":"AMBRurl"}
  - {"fx_name":"Small Town Beach Distant Traffic Morning France","description":"SAINT TROPEZ - Beach in the morning. Water waves splatter, crickets and distant traffic throughout. Occasional ship engine hum.","category":"AMBIENCE/SEASIDE","cat_id":"AMBSea"}
