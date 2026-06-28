# AI Alias Prompt Preview

This file is a local input preview. No AI service was called.

- mode: `new_candidate`

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

## Item 1: Gun

- canonical: `Gun`
- slot: `object`
- candidate_type: `token`
- record_count: `2376`
- AI instruction: Generate conservative Chinese aliases for a sound-design FXName token. Do not translate freely. Return only aliases that a Chinese sound designer would actually type.
- examples:
  - {"fx_name":"Long Gun 150m","description":"Antique artillery, historic cannon long gun, cal 38mm. ORTF3D Hi positioned 150m away from the cannon.","category":"GUNS/CANNON","cat_id":"GUNCano"}
  - {"fx_name":"Long Gun 175m","description":"Antique artillery, historic cannon long gun, cal 38mm. XY handheld recorder positioned 175m away from the cannon.","category":"GUNS/CANNON","cat_id":"GUNCano"}
  - {"fx_name":"Long Gun 1m","description":"Antique artillery, historic cannon long gun, cal 38mm. Small AB positioned 1m away from the cannon.","category":"GUNS/CANNON","cat_id":"GUNCano"}

## Item 2: Hit

- canonical: `Hit`
- slot: `action`
- candidate_type: `token`
- record_count: `1418`
- AI instruction: Generate conservative Chinese aliases for a sound-design FXName token. Do not translate freely. Return only aliases that a Chinese sound designer would actually type.
- examples:
  - {"fx_name":"Basic Hit Old School","description":"Traditional punch sound with a vintage feel.","category":"FIGHT/IMPACT","cat_id":"FGHTImpt"}
  - {"fx_name":"Slap Hit","description":"Punch noise reminiscent of a slap impact.","category":"FIGHT/IMPACT","cat_id":"FGHTImpt"}
  - {"fx_name":"Button Box Case Hit","description":"Impact of a metal object striking a button box case.","category":"METAL/IMPACT","cat_id":"METLImpt"}

## Item 3: Squeak

- canonical: `Squeak`
- slot: `action`
- candidate_type: `token`
- record_count: `172`
- AI instruction: Generate conservative Chinese aliases for a sound-design FXName token. Do not translate freely. Return only aliases that a Chinese sound designer would actually type.
- examples:
  - {"fx_name":"Dog Toy Chew Teething Ball Squeak Sequence","description":"Squeaking sequences of a dog chew ball for teething being squeezed.","category":"CARTOON/SQUEAK","cat_id":"TOONSqk"}
  - {"fx_name":"Metal Squeak Constant Fast","description":"Continuous, quick movement with sliding, rattling, squeaking and some ringing.","category":"GUNS/CANNON","cat_id":"METLFric"}
  - {"fx_name":"Metal Squeak Constant Moderate","description":"Continuous, medium fast movement with sliding, rattling, squeaking and some ringing.","category":"GUNS/CANNON","cat_id":"METLFric"}

## Item 4: Crack

- canonical: `Crack`
- slot: `action`
- candidate_type: `token`
- record_count: `114`
- AI instruction: Generate conservative Chinese aliases for a sound-design FXName token. Do not translate freely. Return only aliases that a Chinese sound designer would actually type.
- examples:
  - {"fx_name":"Tight Crack","description":"Brief explosion noise reminiscent of a sharp crack.","category":"EXPLOSIONS/REAL","cat_id":"EXPLReal"}
  - {"fx_name":"Crack Fruit Box","description":"Wooden fruit box cracking characterized by its sharp and splintering nature.","category":"WOOD/BREAK","cat_id":"WOODBrk"}
  - {"fx_name":"Crack Mining Crystals","description":"Rugged crack and fracture as a stone breaks upon impact.","category":"ROCKS/IMPACT","cat_id":"ROCKImpt"}

## Item 5: Single Shot

- canonical: `Single Shot`
- slot: `action`
- candidate_type: `phrase`
- record_count: `875`
- AI instruction: Generate conservative Chinese aliases for a sound-design FXName token. Do not translate freely. Return only aliases that a Chinese sound designer would actually type.
- examples:
  - {"fx_name":"AK47 V1 Single Shot 01 2m","description":"Avtomat Kalashnikova, Kalashnikov AK-47, Assault Rifle, cal. 7.62 x 39mm, 6 variations. A/B with dynamic mics positioned very close, 2 mete…","category":"GUNS/RIFLE","cat_id":"GUNRif"}
  - {"fx_name":"AK47 V1 Single Shot 01 30m","description":"Avtomat Kalashnikova, Kalashnikov AK-47, Assault Rifle, cal. 7.62 x 39mm, 6 variations. X/Y with supercardiod mics 30m in front of the shoo…","category":"GUNS/RIFLE","cat_id":"GUNRif"}
  - {"fx_name":"AK47 V1 Single Shot 01 3m","description":"Avtomat Kalashnikova, Kalashnikov AK-47, Assault Rifle, cal. 7.62 x 39mm, 6 variations. A/B with cardioid mics positioned close, 3 meter be…","category":"GUNS/RIFLE","cat_id":"GUNRif"}
