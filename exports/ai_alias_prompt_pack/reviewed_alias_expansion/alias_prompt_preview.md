# AI Alias Prompt Preview

This file is a local input preview. No AI service was called.

- mode: `alias_expansion`

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
  - {"fx_name":"Book Large Flick Fast Impact","description":"Rapid flick motion and impact of a large book's pages, resulting in a crisp thud.","category":"PAPER/IMPACT","cat_id":"PAPRImpt"}
  - {"fx_name":"Parcel Moves Impact","description":"Rustling and shifting as the parcel makes contact with another surface or object.","category":"PAPER/IMPACT","cat_id":"PAPRImpt"}
  - {"fx_name":"Filtered Metal Impact Short","description":"Short, sharp thud with a filtered metallic ring.","category":"DESIGNED/IMPACT","cat_id":""}

## Item 2: Friction

- canonical: `Friction`
- slot: `action`
- candidate_type: `token`
- record_count: `231`
- AI instruction: Generate conservative Chinese aliases for a sound-design FXName token. Do not translate freely. Return only aliases that a Chinese sound designer would actually type.
- examples:
  - {"fx_name":"Concert Bass Large Friction Egg Mallet","description":"Rich, deep sound from a large friction egg mallet on concert bass.","category":"RUBBER/FRICTION","cat_id":""}
  - {"fx_name":"Concert Bass Large Friction Scrape Long","description":"Extended, resonant friction scrape on a large concert bass.","category":"RUBBER/FRICTION","cat_id":""}
  - {"fx_name":"Concert Bass Large Friction Scrape Short","description":"Brief, sharp friction scrape on a large concert bass.","category":"RUBBER/FRICTION","cat_id":""}

## Item 3: Gun

- canonical: `Gun`
- slot: `object`
- candidate_type: `token`
- record_count: `2376`
- AI instruction: Generate conservative Chinese aliases for a sound-design FXName token. Do not translate freely. Return only aliases that a Chinese sound designer would actually type.
- examples:
  - {"fx_name":"Long Gun 150m","description":"Antique artillery, historic cannon long gun, cal 38mm. ORTF3D Hi positioned 150m away from the cannon.","category":"GUNS/CANNON","cat_id":"GUNCano"}
  - {"fx_name":"Long Gun 175m","description":"Antique artillery, historic cannon long gun, cal 38mm. XY handheld recorder positioned 175m away from the cannon.","category":"GUNS/CANNON","cat_id":"GUNCano"}
  - {"fx_name":"Long Gun 1m","description":"Antique artillery, historic cannon long gun, cal 38mm. Small AB positioned 1m away from the cannon.","category":"GUNS/CANNON","cat_id":"GUNCano"}

## Item 4: Hit

- canonical: `Hit`
- slot: `action`
- candidate_type: `token`
- record_count: `1418`
- AI instruction: Generate conservative Chinese aliases for a sound-design FXName token. Do not translate freely. Return only aliases that a Chinese sound designer would actually type.
- examples:
  - {"fx_name":"Basic Hit Old School","description":"Traditional punch sound with a vintage feel.","category":"FIGHT/IMPACT","cat_id":"FGHTImpt"}
  - {"fx_name":"Slap Hit","description":"Punch noise reminiscent of a slap impact.","category":"FIGHT/IMPACT","cat_id":"FGHTImpt"}
  - {"fx_name":"Button Box Case Hit","description":"Impact of a metal object striking a button box case.","category":"METAL/IMPACT","cat_id":"METLImpt"}

## Item 5: Squeak

- canonical: `Squeak`
- slot: `action`
- candidate_type: `token`
- record_count: `172`
- AI instruction: Generate conservative Chinese aliases for a sound-design FXName token. Do not translate freely. Return only aliases that a Chinese sound designer would actually type.
- examples:
  - {"fx_name":"Dog Toy Chew Teething Ball Squeak Sequence","description":"Squeaking sequences of a dog chew ball for teething being squeezed.","category":"CARTOON/SQUEAK","cat_id":"TOONSqk"}
  - {"fx_name":"Metal Squeak Constant Fast","description":"Continuous, quick movement with sliding, rattling, squeaking and some ringing.","category":"GUNS/CANNON","cat_id":"METLFric"}
  - {"fx_name":"Metal Squeak Constant Moderate","description":"Continuous, medium fast movement with sliding, rattling, squeaking and some ringing.","category":"GUNS/CANNON","cat_id":"METLFric"}

## Item 6: Shot

- canonical: `Shot`
- slot: `action`
- candidate_type: `token`
- record_count: `1360`
- AI instruction: Generate conservative Chinese aliases for a sound-design FXName token. Do not translate freely. Return only aliases that a Chinese sound designer would actually type.
- examples:
  - {"fx_name":"Sweetener Distortion Shot Low Texture","description":"Processed noise to enhance shots. Rumbling and stuttering.","category":"GUNS/CANNON","cat_id":"GUNCano"}
  - {"fx_name":"Sweetener Shot Airy","description":"Processed shot with heavy detonation and dense tail.","category":"GUNS/CANNON","cat_id":"GUNCano"}
  - {"fx_name":"Sweetener Shot Clean","description":"Processed shot with tight detonation and soft tail.","category":"GUNS/CANNON","cat_id":"GUNCano"}

## Item 7: Chain

- canonical: `Chain`
- slot: `object`
- candidate_type: `token`
- record_count: `190`
- AI instruction: Generate conservative Chinese aliases for a sound-design FXName token. Do not translate freely. Return only aliases that a Chinese sound designer would actually type.
- examples:
  - {"fx_name":"Chain Big","description":"Large movement for chain shot.","category":"GUNS/CANNON","cat_id":"CHAINImpt"}
  - {"fx_name":"Chain Bright","description":"Fast movement for chain shot.","category":"GUNS/CANNON","cat_id":"CHAINImpt"}
  - {"fx_name":"Chain Constant Big","description":"Continuous clanging and rattling. Large and steady.","category":"GUNS/CANNON","cat_id":"CHAINMvmt"}

## Item 8: Crack

- canonical: `Crack`
- slot: `action`
- candidate_type: `token`
- record_count: `114`
- AI instruction: Generate conservative Chinese aliases for a sound-design FXName token. Do not translate freely. Return only aliases that a Chinese sound designer would actually type.
- examples:
  - {"fx_name":"Tight Crack","description":"Brief explosion noise reminiscent of a sharp crack.","category":"EXPLOSIONS/REAL","cat_id":"EXPLReal"}
  - {"fx_name":"Crack Fruit Box","description":"Wooden fruit box cracking characterized by its sharp and splintering nature.","category":"WOOD/BREAK","cat_id":"WOODBrk"}
  - {"fx_name":"Crack Mining Crystals","description":"Rugged crack and fracture as a stone breaks upon impact.","category":"ROCKS/IMPACT","cat_id":"ROCKImpt"}

## Item 9: Door

- canonical: `Door`
- slot: `object`
- candidate_type: `token`
- record_count: `483`
- AI instruction: Generate conservative Chinese aliases for a sound-design FXName token. Do not translate freely. Return only aliases that a Chinese sound designer would actually type.
- examples:
  - {"fx_name":"Microwave Door Clunk Close","description":"Microwave door being closed with a thud and additional click.","category":"DOORS/APPLIANCE","cat_id":"DOORAppl"}
  - {"fx_name":"Microwave Door Clunk Open","description":"Microwave door being opened with a thud and additional tonal click.","category":"DOORS/APPLIANCE","cat_id":"DOORAppl"}
  - {"fx_name":"Microwave Door Impact","description":"Microwave door being closed with hard intensity. Impactful closure of a microwave door with some additional rattling.","category":"DOORS/APPLIANCE","cat_id":"DOORAppl"}

## Item 10: Drop

- canonical: `Drop`
- slot: `action`
- candidate_type: `token`
- record_count: `248`
- AI instruction: Generate conservative Chinese aliases for a sound-design FXName token. Do not translate freely. Return only aliases that a Chinese sound designer would actually type.
- examples:
  - {"fx_name":"Metal Chain Drop","description":"Longer sequence of metallic chain being dropped.","category":"GUNS/CANNON","cat_id":"CHAINMvmt"}
  - {"fx_name":"Metal Chain Drop High","description":"Metallic chain being dropped with high, tonal ring out.","category":"GUNS/CANNON","cat_id":"CHAINMvmt"}
  - {"fx_name":"Metal Chain Drop High Ringing","description":"Metallic chain being dropped with tonal ring out.","category":"GUNS/CANNON","cat_id":"CHAINMvmt"}

## Item 11: Ring

- canonical: `Ring`
- slot: `action`
- candidate_type: `token`
- record_count: `164`
- AI instruction: Generate conservative Chinese aliases for a sound-design FXName token. Do not translate freely. Return only aliases that a Chinese sound designer would actually type.
- examples:
  - {"fx_name":"Gong Hit Ring Out Long","description":"Soft, long, and vibrating sound with feedback.","category":"MUSICAL/PERCUSSION","cat_id":"MUSCPerc"}
  - {"fx_name":"Gong Hits Small Hard Ring Out","description":"Hard strike is producing vibration with feedback.","category":"MUSICAL/PERCUSSION","cat_id":"MUSCPerc"}
  - {"fx_name":"Gong Hits Small Slow Ring Out","description":"Soft and long vibration with feedback.","category":"MUSICAL/PERCUSSION","cat_id":"MUSCPerc"}

## Item 12: Single Shot

- canonical: `Single Shot`
- slot: `action`
- candidate_type: `phrase`
- record_count: `875`
- AI instruction: Generate conservative Chinese aliases for a sound-design FXName token. Do not translate freely. Return only aliases that a Chinese sound designer would actually type.
- examples:
  - {"fx_name":"AK47 V1 Single Shot 01 2m","description":"Avtomat Kalashnikova, Kalashnikov AK-47, Assault Rifle, cal. 7.62 x 39mm, 6 variations. A/B with dynamic mics positioned very close, 2 mete…","category":"GUNS/RIFLE","cat_id":"GUNRif"}
  - {"fx_name":"AK47 V1 Single Shot 01 30m","description":"Avtomat Kalashnikova, Kalashnikov AK-47, Assault Rifle, cal. 7.62 x 39mm, 6 variations. X/Y with supercardiod mics 30m in front of the shoo…","category":"GUNS/RIFLE","cat_id":"GUNRif"}
  - {"fx_name":"AK47 V1 Single Shot 01 3m","description":"Avtomat Kalashnikova, Kalashnikov AK-47, Assault Rifle, cal. 7.62 x 39mm, 6 variations. A/B with cardioid mics positioned close, 3 meter be…","category":"GUNS/RIFLE","cat_id":"GUNRif"}
