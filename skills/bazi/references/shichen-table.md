# Double-hours, day pillar, hour pillar

## The twelve double-hours (时辰)

| Branch | Time | Name |
|---|---|---|
| 子 Zi | 23:00-01:00 | midnight |
| 丑 Chou | 01:00-03:00 | cockcrow |
| 寅 Yin | 03:00-05:00 | dawn |
| 卯 Mao | 05:00-07:00 | sunrise |
| 辰 Chen | 07:00-09:00 | breakfast |
| 巳 Si | 09:00-11:00 | late morning |
| 午 Wu | 11:00-13:00 | noon |
| 未 Wei | 13:00-15:00 | early afternoon |
| 申 Shen | 15:00-17:00 | afternoon |
| 酉 You | 17:00-19:00 | sunset |
| 戌 Xu | 19:00-21:00 | dusk |
| 亥 Hai | 21:00-23:00 | night |

Rough descriptions: before dawn → 丑/寅; early morning → 卯; morning → 辰/巳; midday → 午; afternoon → 未/申; evening → 酉/戌; night → 亥; deep night → 子.

Birthplace gives a true-solar-time correction (about 4 minutes per degree of longitude from the time-zone meridian). Mention it as a reference; apply it only if the user gives an exact time and wants it.

## Early and late Zi
- 00:00-01:00 (early Zi): same day's day pillar.
- 23:00-24:00 (late Zi): hour branch is 子, and the hour stem uses the **next** day's day stem. This skill uses that convention; say so when it matters.

## Day pillar formula
1. Compute the Julian Day Number `JDN` for the Gregorian date (use the date as given, at noon):
   `a=(14-month)//12; y=year+4800-a; m=month+12a-3; JDN=day+(153m+2)//5+365y+y//4-y//100+y//400-32045`
2. `index = (JDN + 49) mod 60`, where 0 = 甲子, 1 = 乙丑, ... 59 = 癸亥.
3. Stem = `index mod 10` in 甲乙丙丁戊己庚辛壬癸; branch = `index mod 12` in 子丑寅卯辰巳午未申酉戌亥.
4. Check: 2000-01-01 → 戊午 (index 54).

## Hour stem (five-rat rule 五鼠遁元)
"甲己 start 甲子; 乙庚 start 丙子; 丙辛 start 戊子; 丁壬 start 庚子; 戊癸 start 壬子."

| Day stem | 子 | 丑 | 寅 | 卯 | 辰 | 巳 | 午 | 未 | 申 | 酉 | 戌 | 亥 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 甲/己 | 甲子 | 乙丑 | 丙寅 | 丁卯 | 戊辰 | 己巳 | 庚午 | 辛未 | 壬申 | 癸酉 | 甲戌 | 乙亥 |
| 乙/庚 | 丙子 | 丁丑 | 戊寅 | 己卯 | 庚辰 | 辛巳 | 壬午 | 癸未 | 甲申 | 乙酉 | 丙戌 | 丁亥 |
| 丙/辛 | 戊子 | 己丑 | 庚寅 | 辛卯 | 壬辰 | 癸巳 | 甲午 | 乙未 | 丙申 | 丁酉 | 戊戌 | 己亥 |
| 丁/壬 | 庚子 | 辛丑 | 壬寅 | 癸卯 | 甲辰 | 乙巳 | 丙午 | 丁未 | 戊申 | 己酉 | 庚戌 | 辛亥 |
| 戊/癸 | 壬子 | 癸丑 | 甲寅 | 乙卯 | 丙辰 | 丁巳 | 戊午 | 己未 | 庚申 | 辛酉 | 壬戌 | 癸亥 |
