# BOOM Candidate Evidence Report

- input token count: `500`
- input phrase count: `500`
- action candidate count: `15`
- object candidate count: `12`
- material candidate count: `11`
- detail/modifier candidate count: `15`
- phrase candidate count: `4`
- rejected noise count: `943`
- review-only candidates written: `0`

## Top accepted examples

- `metal` (token, material): score=80, records=1735
- `impact` (token, action): score=80, records=1552
- `wood` (token, material): score=75, records=939
- `gun` (token, object): score=70, records=2376
- `whoosh` (token, action): score=70, records=1564
- `car` (token, object): score=70, records=1470
- `hit` (token, action): score=70, records=1418
- `plastic` (token, material): score=70, records=437
- `leather` (token, material): score=70, records=260
- `friction` (token, action): score=70, records=231

## Top review examples

- `gun shot` (phrase, action): score=80, records=183
- `projectile gun shot` (phrase, action): score=80, records=176
- `shot` (token, action): score=70, records=1360
- `cannon` (token, object): score=70, records=1257
- `scrape` (token, action): score=65, records=699
- `hard hit` (phrase, action): score=65, records=161
- `tonal` (token, detail): score=60, records=1456
- `single shot` (phrase, action): score=60, records=875
- `rattle` (token, action): score=60, records=487
- `door` (token, object): score=60, records=483

## Top rejected examples

- `burst` (token, unknown): score=35, records=643
- `long gun` (phrase, unknown): score=35, records=125
- `movement` (token, unknown): score=30, records=1671
- `shotgun` (token, unknown): score=30, records=1248
- `medium` (token, unknown): score=30, records=1217
- `small` (token, unknown): score=30, records=1090
- `train` (token, unknown): score=30, records=436
- `debris` (token, unknown): score=30, records=384
- `female` (token, unknown): score=30, records=366
- `rock` (token, unknown): score=30, records=286

## Scoring rule summary

- record frequency: +10/+15/+20/+25 at 20/100/500/1000 records
- field diversity >= 1.5: +10
- appears in FXName: +15
- known action/object/material vocabulary: +20
- category/subcategory alignment: +10
- phrase ending in action: +15; source + action: +20
- metadata/code: -30; library context: -25; mic/spec: -40
- detail-only: -20; unnatural phrase order: -15
- score >= 70 candidate; 40-69 review; below 40 reject
- review-only and hard-reject policies override numeric thresholds

## Canonical token guard

- canonical_tokens_sha256_before: `A7981F8BBED28C33038F5C5DEF267952EE78EFEC80CDE5DB7313F17EB1E5FE9E`
- canonical_tokens_sha256_after: `A7981F8BBED28C33038F5C5DEF267952EE78EFEC80CDE5DB7313F17EB1E5FE9E`
- canonical_tokens.csv changed: `no`
- automatic promotion: `no`
