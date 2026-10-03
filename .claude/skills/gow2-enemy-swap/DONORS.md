# Where to pull creatures from (donor levels)

Generated from the pack index. A creature's pool block must be copied from a level that already
uses it. `block GO+MEM` is the number of 8-byte object-pool and memory-pool entries; two creatures
with the same shape can be swapped in place with a hex editor without touching the offset tables.
Sizes are the creature WAD payload (memory budget, manual section 8).

| creature | WAD | KB | block GO+MEM | donor levels (max N first) |
|---|---|---|---|---|
| Archer10 | R_ARCHER10.WAD | 829 | 14+15 | ISLE40 (N=9), PAL70 (N=5), ISLE10 (N=4), PEGA50 (N=4) |
| Bkarmy00 | R_BKARMY00.WAD | 596 | 23+13 | BOG250 (N=5) |
| Boar00 | R_BOAR00.WAD | 495 | 7+13 | BOG10 (N=2), ISLE30 (N=2) |
| Boatlow | R_BOATLOW.WAD | 397 | 15+13 | BOG250 (N=1) |
| Bones00 | R_BONES00.WAD | 663 | 7+13 | PAL60 (N=13), BOG10 (N=8), BOG90 (N=8), PAL80 (N=7) |
| Bug10 | R_BUG10.WAD | 518 | 15+16 | ISLE42 (N=4), PAL10 (N=4), CMBT31 (N=2), CMBT32 (N=2) |
| Bug20 | R_BUG20.WAD | 393 | 9+16 | PAL45 (N=8), ISLE14 (N=7), ATLAS240 (N=5), BOG30 (N=5) |
| Captan00 | R_CAPTAN00.WAD | 822 | 7+13 | CMBT21 (N=3), CMBT22 (N=3), CMBT23 (N=3), ISLE40 (N=3) |
| Captan10 | R_CAPTAN10.WAD | 864 | 7+13 | PAL85 (N=5), ATLAS230 (N=2) |
| Cerbus00 | R_CERBUS00.WAD | 1166 | 19+15 | PAL50 (N=5) |
| Cerbus10 | R_CERBUS10.WAD | 1341 | 28+15 | CMBT61 (N=4), CMBT62 (N=4), CMBT63 (N=4), ISLE10 (N=1) |
| Cerbus20 | R_CERBUS20.WAD | 1127 | 13+15 | BOG45 (N=1) |
| Cerpup00 | R_CERPUP00.WAD | 801 | 20+14 | PAL50 (N=6), FREE11 (N=3), FREE12 (N=3), FREE13 (N=3) |
| Colsus00 | R_COLSUS00.WAD | 2965 | 28+11 | RHOD10 (N=1) |
| Colsus01 | R_COLSUS01.WAD | 3952 | 35+11 | RHOD23 (N=1) |
| Colsus02 | R_COLSUS02.WAD | 1066 | 4+11 | RHOD27 (N=1) |
| Colsus03 | R_COLSUS03.WAD | 2194 | 24+11 | RHOD30 (N=1) |
| Cyclop00 | R_CYCLOP00.WAD | 1107 | 6+14 | CMBT41 (N=4), CMBT42 (N=4), CMBT43 (N=4), PAL15 (N=2) |
| Cyclop01 | R_CYCLOP01.WAD | 895 | 7+14 | ISLE30 (N=2), CMBT31 (N=1), CMBT32 (N=1), CMBT33 (N=1) |
| Cyclop30 | R_CYCLOP30.WAD | 1469 | 19+13 | CMBT11 (N=2), CMBT12 (N=2), CMBT13 (N=2), CMBT71 (N=2) |
| Deadb00 | R_DEADB00.WAD | 186 | 1+12 | BOG35 (N=1), ISLE06 (N=1) |
| DeadbFloat00 |  | 0 | 1+8 | PAL43 (N=15) |
| Deadbsp | R_DEADBSP.WAD | 176 | 1+12 | PAL17 (N=1) |
| FatMed |  | 0 | 37+21 | BOG80 (N=1) |
| Grifin00 | R_GRIFIN00.WAD | 1171 | 11+10 | PEGA70 (N=4), PEGA10 (N=3) |
| Grifin01 | R_GRIFIN01.WAD | 543 | 7+9 | PEGA70 (N=10), PEGA10 (N=9) |
| Grifin02 | R_GRIFIN02.WAD | 426 | 7+9 | PEGA70 (N=16), PEGA10 (N=10) |
| Grifin10 | R_GRIFIN10.WAD | 1893 | 24+10 | PEGA30 (N=1), PEGA79 (N=1) |
| Harpy00 | R_HARPY00.WAD | 617 | 10+14 | PEGA40 (N=6), PEGA50 (N=5) |
| Harpy10 | R_HARPY10.WAD | 773 | 19+15 | ISLE46 (N=6), BOG87 (N=4) |
| Harpy20 | R_HARPY20.WAD | 826 | 19+15 | ATLAS210 (N=8), CMBT51 (N=8), CMBT52 (N=8), CMBT53 (N=8) |
| Harpy30 | R_HARPY30.WAD | 616 | 11+15 | ISLE20 (N=3), ISLE45 (N=3) |
| Harpy40 | R_HARPY40.WAD | 321 | 2+8 | PEGA70 (N=16), PEGA35 (N=12), PEGA30 (N=8) |
| Icarus | R_ICARUS.WAD | 1426 | 7+13 | BOG225 (N=2), BOG220 (N=1) |
| Kraken | R_KRAKEN.WAD | 4624 | 48+12 | PAL17 (N=1) |
| Kraken10 | R_KRAKEN10.WAD | 972 | 1+9 | PAL17 (N=1) |
| Medusa00 | R_MEDUSA00.WAD | 1311 | 11+19 | RHOD10 (N=8), PEGA50 (N=3) |
| Medusa10 | R_MEDUSA10.WAD | 1268 | 12+19 | BOG45 (N=2), PAL70 (N=2), CMBT31 (N=1), CMBT32 (N=1) |
| Medusa20 | R_MEDUSA20.WAD | 1324 | 14+21 | SPIR37 (N=4), CMBT21 (N=1), CMBT22 (N=1), CMBT23 (N=1) |
| Mintar00 | R_MINTAR00.WAD | 962 | 13+13 | ISLE44 (N=3), CMBT31 (N=2), CMBT32 (N=2), CMBT33 (N=2) |
| Mintar30 | R_MINTAR30.WAD | 1012 | 24+14 | CMBT61 (N=4), CMBT62 (N=4), CMBT63 (N=4), SPIR38 (N=4) |
| Mintar40 | R_MINTAR40.WAD | 1069 | 13+13 | PEGA45 (N=3), PEGA40 (N=1) |
| Mintar41 | R_MINTAR41.WAD | 1068 | 13+13 | ISLE20 (N=3) |
| Mrhand00 | R_MRHAND00.WAD | 202 | 9+13 | RHOD55 (N=42) |
| Orderl00 | R_ORDERL00.WAD | 864 | 22+13 | CMBT51 (N=6), CMBT52 (N=6), CMBT53 (N=6), SPIR37 (N=3) |
| Orderl10 | R_ORDERL10.WAD | 909 | 22+13 | BOG220 (N=2), BOG85 (N=2), CMBT21 (N=1), CMBT22 (N=1) |
| Orderp00 | R_ORDERP00.WAD | 854 | 17+15 | CMBT61 (N=10), CMBT62 (N=10), CMBT63 (N=10), BOG35 (N=4) |
| Orders00 | R_ORDERS00.WAD | 902 | 13+13 | BOG210 (N=7), PAL30 (N=6), PEGA50 (N=4), PEGA52 (N=4) |
| Orders01 | R_ORDERS01.WAD | 1012 | 13+13 | BOG30 (N=6), BOG40 (N=6) |
| Orders02 | R_ORDERS02.WAD | 1144 | 13+13 | ATLAS235 (N=6), ISLE10 (N=6), PEGA40 (N=6), ATLAS230 (N=5) |
| Orders05 | R_ORDERS05.WAD | 1255 | 13+13 | PAL70 (N=6), PEGA45 (N=4) |
| Orders10 | R_ORDERS10.WAD | 841 | 13+13 | ISLE46 (N=9), RHOD10 (N=9), ATLAS250 (N=7), ISLE06 (N=5) |
| Perseus |  | 0 | 27+14 | ISLE47 (N=1) |
| Phoenix | R_PHOENIX.WAD | 707 | 27+9 | PAL97 (N=1) |
| Phoenix10 | R_PHOENIX10.WAD | 459 | 27+9 | PAL15 (N=3), PAL17 (N=1) |
| Priest10 | R_PRIEST10.WAD | 1372 | 37+15 | CMBT61 (N=3), CMBT62 (N=3), CMBT63 (N=3), ISLE44 (N=3) |
| Prome00 | R_PROME00.WAD | 473 | 4+13 | PEGA45 (N=1) |
| Rabdog00 | R_RABDOG00.WAD | 468 | 6+13 | CMBT41 (N=12), CMBT42 (N=12), CMBT43 (N=12), ISLE06 (N=10) |
| Raven00 | R_RAVEN00.WAD | 456 | 8+9 | PEGA70 (N=2), PEGA30 (N=1) |
| Rharch00 | R_RHARCH00.WAD | 545 | 11+14 | RHOD25 (N=5), RHOD27 (N=5) |
| Rhsold00 | R_RHSOLD00.WAD | 544 | 7+14 | RHOD10 (N=16), RHOD27 (N=8), RHOD20 (N=6), RHOD25 (N=6) |
| Rider00 | R_RIDER00.WAD | 522 | 2+13 | PEGA70 (N=5) |
| Rider10 | R_RIDER10.WAD | 680 | 2+13 | PEGA30 (N=1), PEGA79 (N=1) |
| Rock00 | R_ROCK00.WAD | 1084 | 24+15 | BOG40 (N=1) |
| Rock01 | R_ROCK01.WAD | 925 | 23+15 | ATLAS220 (N=1) |
| Rock10 | R_ROCK10.WAD | 1079 | 24+15 | BOG90 (N=1), CMBT71 (N=1), CMBT72 (N=1), CMBT73 (N=1) |
| S3Hand00 | R_S3HAND00.WAD | 52 | 1+10 | SPIR40 (N=1) |
| S3Hand01 | R_S3HAND01.WAD | 50 | 1+10 | SPIR40 (N=1) |
| S3Hand02 | R_S3HAND02.WAD | 43 | 1+10 | SPIR40 (N=1) |
| S3Hand03 | R_S3HAND03.WAD | 43 | 1+10 | SPIR40 (N=1) |
| S3Hand04 | R_S3HAND04.WAD | 55 | 1+10 | SPIR40 (N=1) |
| S3Hand05 | R_S3HAND05.WAD | 52 | 1+10 | SPIR40 (N=1) |
| S3Hand06 | R_S3HAND06.WAD | 49 | 1+10 | SPIR40 (N=1) |
| Satyr00 | R_SATYR00.WAD | 869 | 12+13 | CMBT41 (N=6), CMBT42 (N=6), CMBT43 (N=6), SPIR38 (N=4) |
| Satyr10 | R_SATYR10.WAD | 790 | 9+13 | RHOD10 (N=16), ATLAS220 (N=2), ISLE45 (N=2) |
| Siren00 | R_SIREN00.WAD | 897 | 21+15 | CMBT41 (N=6), CMBT42 (N=6), CMBT43 (N=6), CMBT51 (N=6) |
| Siren10 | R_SIREN10.WAD | 867 | 13+15 | ISLE12 (N=3), ZEUS10 (N=3), RHOD10 (N=3), PAL40 (N=2) |
| Sister01 |  | 0 | 26+15 | SPIR20 (N=1) |
| Sister02 | R_SISTER02.WAD | 1928 | 26+16 | SPIR20 (N=1) |
| Sister3A | R_SISTER3A.WAD | 1181 | 5+13 | SPIR40 (N=1) |
| Sister3B | R_SISTER3B.WAD | 723 | 5+13 | SPIR40 (N=1) |
| Sister3C | R_SISTER3C.WAD | 1584 | 7+11 | SPIR40 (N=1) |
| Skelly00 | R_SKELLY00.WAD | 816 | 9+15 | PAL30 (N=6), PAL90 (N=6), BOG245 (N=2) |
| Skelly10 | R_SKELLY10.WAD | 849 | 16+13 | BOG70 (N=14), SPIR35 (N=6) |
| Spartan | R_SPARTAN.WAD | 394 | 5+13 | PAL17 (N=1) |
| SpireBell00 |  | 0 | 5+13 | SPIR10 (N=2) |
| Spsold10 | R_SPSOLD10.WAD | 203 | 1+10 | BOG45 (N=1) |
| Theseus | R_THESEUS.WAD | 1263 | 16+14 | ISLE20 (N=1) |
| Train00 | R_TRAIN00.WAD | 858 | 18+13 | CMBT71 (N=6), CMBT72 (N=6), CMBT73 (N=6), BOG20 (N=4) |
| Trold00 | R_TROLD00.WAD | 1297 | 5+13 | PAL40 (N=2) |
| Tryng00 | R_TRYNG00.WAD | 1268 | 5+14 | CMBT41 (N=1), CMBT42 (N=1), CMBT43 (N=1), PAL25 (N=1) |
| Twin00 | R_TWIN00.WAD | 338 | 2+12 | RHOD15 (N=1) |
| Twin01 | R_TWIN01.WAD | 294 | 2+12 | RHOD15 (N=1) |
| Wraith00 | R_WRAITH00.WAD | 733 | 18+13 | CMBT51 (N=6), CMBT52 (N=6), CMBT53 (N=6), ISLE16 (N=3) |
| Wraith10 | R_WRAITH10.WAD | 845 | 24+13 | CMBT61 (N=10), CMBT62 (N=10), CMBT63 (N=10), ISLE42 (N=3) |
| Zeus |  | 0 | 31+16 | ZEUS10 (N=2) |
| Zeusbig | R_ZEUSBIG.WAD | 2075 | 17+13 | ZEUS10 (N=1) |
| Zeusswd | R_ZEUSSWD.WAD | 613 | 1+12 | RHOD50 (N=1) |
