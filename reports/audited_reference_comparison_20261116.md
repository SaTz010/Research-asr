# Published versus human-reviewed references — 50-clip audit

Computed November 16, 2026 from frozen reviews and saved local/API predictions. No new ASR, network or credential access is needed.

## What changed

- 42 references are unchanged; 8 were edited.
- 8 edits remain after the frozen scoring normalization.
- Published text differs from the human reference by 18 normalized word edits over 979 human-reference words and 54 character edits over 3711 human-reference characters.
- Reference-disagreement WER/CER: 1.84% / 1.46%. These measure text disagreement with the human version as reference, not ASR performance or independently established ground-truth accuracy.

## ASR reference sensitivity — exactly the same 50 clips

The hypotheses are fixed. Only the reference version changes. Corpus totals use total edits / total reference units; corrected references can change denominators. Negative score changes mean lower measured error rates, not necessarily fewer edits.

| System | Reference | Reference words | WER | CER |
|---|---|---:|---:|---:|
| Local Large V2 | published | 974 | 100.82% | 76.30% |
| Local Large V2 | corrected | 979 | 100.41% | 75.83% |
| Whisper API | published | 974 | 94.66% | 80.63% |
| Whisper API | corrected | 979 | 94.18% | 80.19% |

| System | WER change (corrected − published) | CER change |
|---|---:|---:|
| Local Large V2 | -0.41 pp | -0.47 pp |
| Whisper API | -0.48 pp | -0.44 pp |

Word-edit and denominator checks:

- Local Large V2: word edits 982 → 983; reference words 974 → 979.
- Whisper API: word edits 922 → 922; reference words 974 → 979.

A decrease in WER need not mean fewer edit operations: reference content/length changes the denominator while the model hypotheses remain fixed. WER can exceed 100% because insertions count as errors. These 50-clip scores are not the 1,198-clip scores.

Raw-case/punctuation sensitivity is also retained in the JSON output; the table above uses the frozen primary normalization.

## CMI sensitivity

10 audited CMI values differ beyond the ±0.005-point rounding allowance for two-decimal source values. 4 clips change bands: 7, 20, 30, 42.

The published CMI uses source script-based labels; the audited value uses normalized corrected words and human lexical tags, excluding language-independent/other tokens. Differences can reflect reference edits, tokenization, denominator conventions or language judgments. Do not attribute them solely to tag overrides.

| CMI band | Published selection | Human audited |
|---|---:|---:|
| [0,10] | 10 | 11 |
| (10,20] | 10 | 8 |
| (20,30] | 10 | 10 |
| (30,40] | 10 | 13 |
| (40,50] | 10 | 8 |

## All 50 original and reviewed transcripts

The human text is copied from the frozen review without additional editing. Word edits use the human reference as denominator. CMI is displayed to two decimals only here; calculations retain full precision.

| Item | Published dataset transcript | Human-reviewed transcript | Published → audited CMI | Word edits |
|---|---|---|---:|---:|
| 1 | त्यसो भए अब है त्यसो अब हामी के गर्ने विचरण हेर्ने त्यसका लागि हेर्नुहोस् तपाईँलाई नि जुन एउटा quantity को अरूसँग विचरण हेर्न सजिलो हुन्छ त्यहीहरू बनाएर सुरु गर्दा हुन्छ। | त्यसो भए अब है त्यसो अब हामी के गर्ने विचरण हेर्ने त्यसका लागि हेर्नुहोस् तपाईँलाई नि जुन एउटा quantity को अरूसँग विचरण हेर्न सजिलो हुन्छ त्यहीहरू बनाएर सुरु गर्दा हुन्छ। | 3.33 → 3.33 | 0 |
| 2 | X - 10,000 × 6 का मुनि 100 गर्दाखेरि यो तपाईँको कति आयो 19,000 | X - 10,000 × 6 का मुनि 100 गर्दाखेरि यो तपाईँको कति आयो 19,000 | 12.50 → 12.50 | 0 |
| 3 | It equals यसको output चाहिँ 2 आयो अब किन 2 आयो त अब यसको length के छ यसको length पनि | It equals यसको output चाहिँ 2 आयो अब किन 2 आयो त अब यसको length के छ यसको length पनि | 27.78 → 27.78 | 0 |
| 4 | 3 वटा column भयो है त यसरी row and column लाई represent गर्नका लागि चाहिँ हामीले array लाई use गर्न सकिन्छ है | 3 वटा column भयो है त यसरी row and column लाई represent गर्नका लागि चाहिँ हामीले array लाई use गर्न सकिन्छ है | 33.33 → 33.33 | 0 |
| 5 | है matrix कै form मा same matrix नै हो के array 2D array भनेकै matrix हो है अब हेर। | है matrix कै form मा same matrix नै हो के array 2D array भनेकै matrix हो है अब हेर। | 42.11 → 42.11 | 0 |
| 6 | CPU, Mouse, Monitor, RAM, ROM, keyboard, Very Good, Very Good ला। | CPU, Mouse, Monitor, RAM, ROM, keyboard, Very Good, Very Good ला। | 9.09 → 9.09 | 0 |
| 7 | Monitor Next आइ साउड हो ए लसिम रन के टोन आए है | Monitor Next Aayush out हो? ए ल Simran कै turn आयो ल। | 16.67 → 40.00 | 8 |
| 8 | हेमन्तको 1 बिग्रियो ल प्रश्न कस्तो लाग्यो त Time and Work को भन्नुहोस् त Time and Work को प्रश्न कस्तो लाग्यो | हेमन्तको 1 बिग्रियो ल प्रश्न कस्तो लाग्यो त Time and Work को भन्नुहोस् त Time and Work को प्रश्न कस्तो लाग्यो | 30.00 → 30.00 | 0 |
| 9 | यो सबै question दिएको छैन र हेर्नु त unitary method देखि fraction and decimal देखि ratio देखि सबै दिएको छ यदि यो question मा or नभनेर efficiency दियो भने X र Y if गर्ने यहाँ हेर्नुहोस् अब प्रश्न छँदैछ नि | यो सबै question दिएको छैन र हेर्नु त unitary method देखि fraction and decimal देखि ratio देखि सबै दिएको छ यदि यो question मा or नभनेर efficiency दियो भने X र Y if गर्ने यहाँ हेर्नुहोस् अब प्रश्न छँदैछ नि | 32.50 → 32.50 | 0 |
| 10 | 00 cancel ठिक छ 8 × 2 = 16, 16 cancel therefore X को value कति आयो? | 00 cancel ठिक छ 8 × 2 = 16, 16 cancel therefore X को value कति आयो? | 50.00 → 50.00 | 0 |
| 11 | तर जल्ली गणित एकदमै कमजोर छु भन्ने साथीहरू पनि नि जो मसँग अलिक अगाडिदेखि नै join भएर गणित पढिराख्नु भएको छ नि अब तपाईँ के बुझ्नुहोस् तपाईँलाई गणितमा जस्तो प्रश्न सोधे पनि गाह्रो लाग्दैन | तर जल्ली गणित एकदमै कमजोर छु भन्ने साथीहरू पनि नि जो मसँग अलिक अगाडिदेखि नै join भएर गणित पढिराख्नु भएको छ नि अब तपाईँ के बुझ्नुहोस् तपाईँलाई गणितमा जस्तो प्रश्न सोधे पनि गाह्रो लाग्दैन | 2.94 → 2.94 | 0 |
| 12 | A र B ले सँगै कति दिन काम गरे त A र B ले सँगै X दिन काम गरे यो भनेको बुझिन्छ कि बुझिँदैन भन्नुहोस् त भन्नुहोस् | A र B ले सँगै कति दिन काम गरे त A र B ले सँगै X दिन काम गरे यो भनेको बुझिन्छ कि बुझिँदैन भन्नुहोस् त भन्नुहोस् | 18.52 → 18.52 | 0 |
| 13 | यहाँबाट X निकाल्नका लागि 43904 लाई 1.75616 ले divide गर्नु त | यहाँबाट X निकाल्नका लागि 43904 लाई 1.75616 ले divide गर्नु त | 22.22 → 22.22 | 0 |
| 14 | E र L चाहिँ के हुनु पऱ्यो delete हुनु पऱ्यो र E र L delete भएपछि आउनु पऱ्यो HLO को रूपमा चाहिँ हाम्रो output आएको छ यसरी चाहिँ हाम्रो specific index केही specific index को data लाई | E र L चाहिँ के हुनु पऱ्यो delete हुनु पऱ्यो र E र L delete भएपछि आउनु पऱ्यो HLO को रूपमा चाहिँ हाम्रो output आएको छ यसरी चाहिँ हाम्रो specific index केही specific index को data लाई | 35.14 → 35.14 | 0 |
| 15 | Okay row 0 and column 3, 3 भयो होइन यसरी चाहिँ यहाँनिर देख्न सक्छौँ row 0 | Okay row 0 and column 3, 3 भयो होइन यसरी चाहिँ यहाँनिर देख्न सक्छौँ row 0 | 41.67 → 41.67 | 0 |
| 16 | भन्नेतर्फ लागौँ होइन जहाँनिर चाहिँ हामी देख्न सक्छौँ जुन हाम्रो program छ | भन्नेतर्फ लागौँ होइन जहाँनिर चाहिँ हामी देख्न सक्छौँ जुन हाम्रो program छ | 8.33 → 8.33 | 0 |
| 17 | यदि declare गरिसकेपछि अब हेर हाम्रो loop चलाएर अब 10 वटा एउटा value माग्नु पऱ्यो पो normal तरिकाले माग्न मिल्यो अब 10 वटा value एकैपटक माग्नु पऱ्यो पछि loop चलाउनु पऱ्यो कि परेन | यदि declare गरिसकेपछि अब हेर हाम्रो loop चलाएर अब 10 वटा एउटा value माग्नु पऱ्यो पो normal तरिकाले माग्न मिल्यो अब 10 वटा value एकैपटक माग्नु पऱ्यो पछि loop चलाउनु पऱ्यो कि परेन | 19.35 → 19.35 | 0 |
| 18 | अब यहाँनिर चाहिँ के छ भने हाम्रो जुन hello छ यसलाई चाहिँ हामीले SB.reverse method लाई run गरिसकेपछि अब SB को value हाम्रो के भयो यसको value चाहिँ ठ्याक्कै उल्टो है ठिक छ | अब यहाँनिर चाहिँ के छ भने हाम्रो जुन hello छ यसलाई चाहिँ हामीले SB.reverse method लाई run गरिसकेपछि अब SB को value हाम्रो के भयो यसको value चाहिँ ठ्याक्कै उल्टो है ठिक छ | 21.21 → 23.53 | 0 |
| 19 | 2.50x आयो हो किनभने यो 1.25 को 2 times 2.50x भयो 25% नाफामा बेच्दाको SP अब | 2.50x आयो हो किनभने यो 1.25 को 2 times 2.50x भयो 25% नाफामा बेच्दाको SP अब | 30.77 → 30.77 | 0 |
| 20 | है ल हो L * B - 1/2 * base * height = 96 गरे पनि भइहाल्छ Lal Bahadur ले भने जस्तै कुरो clear | है ल हो L * B - 1/2 * base * height = 96 गरे पनि भइहाल्छ Lal Bahadur ले भने जस्तै कुरो clear | 41.18 → 33.33 | 0 |
| 21 | हो ल यो भने कति भयो भन्नुहोस् त ल कति आउँछ यो 12 साता 84 का मुनि 4 21 0.21 X आ ठिक छ | हो ल यो भने कति भयो भन्नुहोस् त ल कति आउँछ यो 12 साता 84 का मुनि 4 21 0.21 X आ ठिक छ | 5.26 → 5.26 | 0 |
| 22 | तिमी भन्ले hint दिएपछि के गरम था hint न देऊ नका नबोलिकन बसा | तिमी भन्ले hint दिएपछि के गरम था hint न देऊ नका नबोलिकन बसा | 15.38 → 15.38 | 0 |
| 23 | which is not thread state thread को state कुन चाहिँ होइन है new process new process yes right answer and | which is not thread state thread को state कुन चाहिँ होइन है new process new process yes right answer and | 25.00 → 25.00 | 0 |
| 24 | BB right answer अब बाँकी question चाहिँ hardbook सँग related छन् है त जति पनि question हरू छन् अब hardbook सँग related छन् | BB right answer अब बाँकी question चाहिँ hardbook सँग related छन् है त जति पनि question हरू छन् अब hardbook सँग related छन् | 39.13 → 39.13 | 0 |
| 25 | Birse हो | Birse हो | 50.00 → 50.00 | 0 |
| 26 | Okay और task must be service by its deadline period Okay question number 28 hard | Okay A task must be service by its deadline period Okay question number 28 hard | 7.14 → 0.00 | 1 |
| 27 | परिमिति के रहेछ 60 m रहेछ है | परिमिति के रहेछ 60 m रहेछ है | 16.67 → 16.67 | 0 |
| 28 | हेर्नुहोस् त 1 जना महिलाले X दिनमा 1 काम गर्छिन् X को value 320 अतः 1 जना महिलाले | हेर्नुहोस् त 1 जना महिलाले X दिनमा 1 काम गर्छिन् X को value 320 अतः 1 जना महिलाले | 21.43 → 21.43 | 0 |
| 29 | और X भनेको 108 × 3/4 भयो 27 तिया 81 therefore X को value कति आयो त | और X भनेको 108 × 3/4 भयो 27 तिया 81 therefore X को value कति आयो त | 33.33 → 33.33 | 0 |
| 30 | 3 - 30 भयो or ल or अब यो 2 - X भनेको or | 3 का मुनि 30 भयो or ल or अब यो 2 का मुनि X भनेको or | 44.44 → 30.77 | 4 |
| 31 | Velocity और option B right answer the primary role of HDFC is used to | Velocity और option B right answer the primary role of HDFC is used to | 7.14 → 7.14 | 0 |
| 32 | त्यो arguments को रूपमा array लाई pass गरेको हो कि होइन अब त्यस्तै के छ भन्दा त्यो data type पछि त्यो big bracket छ नि त्यो के छ भन्दा अगाडि लेखे पनि भयो अनि त्यसपछि space पछाडि लेखे पनि भयो र last मा लेखे पनि भयो | त्यो arguments को रूपमा array लाई pass गरेको हो कि होइन अब त्यस्तै के छ भन्दा त्यो data type पछि त्यो big bracket छ नि त्यो के छ भन्दा अगाडि लेखे पनि भयो अनि त्यसपछि space पछाडि लेखे पनि भयो र last मा लेखे पनि भयो | 19.57 → 19.57 | 0 |
| 33 | अनि फेरि मैले चाहिँ PS5 के PS5 | अनि फेरि मैले चाहिँ PS5 के PS5 | 28.57 → 28.57 | 0 |
| 34 | 2 भयो अनि अब हेर IG भनेको अब I को value कति छ I को value त increment गरेर 1 भएकोछ अनि J को value कति छ 0 छ | true भयो अनि अब हेर IG भनेको अब I को value कति छ I को value त increment गरेर 1 भएकोछ अनि J को value कति छ 0 छ | 30.77 → 33.33 | 1 |
| 35 | कुन चाहिँ होइन D right answer? | कुन चाहिँ होइन D right answer? | 50.00 → 50.00 | 0 |
| 36 | अब तपाईँले त्यो note को प्रश्न अभ्यास गर्नु भएको छ भने है अभ्यास गर्नु भएको छ भने तपाईँले | अब हेर्नु तपाईँले त्यो note को प्रश्न अभ्यास गर्नु भएको छ भने है अभ्यास गर्नु भएको छ भने तपाईँले | 5.56 → 5.26 | 1 |
| 37 | x - 10,000 भयो ल अब यसमा यसमा अतिरिक्त बिक्रीमा उसले commission कति पाउँछ | x - 10,000 भयो ल अब यसमा यसमा अतिरिक्त बिक्रीमा उसले commission कति पाउँछ | 16.67 → 16.67 | 0 |
| 38 | + 10th सङ्ख्या भनेको x + 1 छ र 11th सङ्ख्या भनेको x छ यति गर्दाखेरि यो कति हाल्ला भन्नुहोस् 160 आयो। | + 10th सङ्ख्या भनेको x + 1 छ र 11th सङ्ख्या भनेको x छ यति गर्दाखेरि यो कति हाल्ला भन्नुहोस् 160 आयो। | 22.22 → 22.22 | 0 |
| 39 | और यहाँबाट X - को value भनेको 160 - 120 भयो यो भनेको therefore X - को value कति आयो त | or यहाँबाट X - को value भनेको 160 - 120 भयो यो भनेको therefore X - को value कति आयो त | 31.25 → 37.50 | 1 |
| 40 | कति थियो solution मा ल case of simple interest है case of simple interest मा है | कति थियो solution मा ल case of simple interest है case of simple interest मा है | 43.75 → 43.75 | 0 |
| 41 | Face Recognition Chat means Autonomous System र DBMS DBMS is right answer. | Face Recognition Chat means Autonomous System र DBMS DBMS is right answer. | 8.33 → 8.33 | 0 |
| 42 | Option C र B Option C wrong answer | Option C or B Option C wrong answer | 12.50 → 0.00 | 1 |
| 43 | अब यहाँ के छ options हरू छ All process have the same priority A task must be served by its deadline period | अब यहाँ के छ options हरू छ All process have the same priority A task must be served by its deadline period | 27.27 → 27.27 | 0 |
| 44 | यहाँनिर string.ins लेखिसकेपछि होइन int main start गर्यो STR1 भनेको चाहिँ हामीले एउटा एउटा destination गर्नको लागि destination कहाँनिर हामीले concat गरिसकेपछि | यहाँनिर string.h लेखिसकेपछि होइन int main start गर्यो STR1 भनेको चाहिँ हामीले एउटा एउटा destination गर्नको लागि destination कहाँनिर हामीले concat गरिसकेपछि | 36.36 → 39.13 | 1 |
| 45 | AI को value A0, A1, A2, A3, A4, A5 मा तिमीले scan गरेको value चाहिँ यसमा आउनेभयो है। | AI को value A0, A1, A2, A3, A4, A5 मा तिमीले scan गरेको value चाहिँ यसमा आउनेभयो है। | 44.44 → 44.44 | 0 |
| 46 | के गरौँ हामी भन्दाखेरि सावा ए सावा बराबर चाहिँ के मानौँ त भन्दाखेरि X मानौँ | के गरौँ हामी भन्दाखेरि सावा ए सावा बराबर चाहिँ के मानौँ त भन्दाखेरि X मानौँ | 6.67 → 6.67 | 0 |
| 47 | कामदार सङ्ख्या प्रतिदिन घन्टा प्रतिदिन per day कति घन्टा काम गर्छ | कामदार सङ्ख्या प्रतिदिन घन्टा प्रतिदिन per day कति घन्टा काम गर्छ | 18.18 → 18.18 | 0 |
| 48 | हजुरसँग मैले class लिन थालेको 20 days भयो 20 दिन भयो confidence एकदम बढेको छ मेरो हो ना Saraswati ji ले definitely बढ्छ मैले तपाईँलाई त्यति detail मा पढाएको छु कि नाम मात्रै command हो है सुरु गरौँ area को विशाल कति साह्रो हो | हजुरसँग मैले class लिन थालेको 20 days भयो 20 दिन भयो confidence एकदम बढेको छ मेरो हो ना Saraswati ji ले definitely बढ्छ मैले तपाईँलाई त्यति detail मा पढाएको छु कि नाम मात्रै command हो है सुरु गरौँ area को विशाल कति साह्रो हो | 21.43 → 21.43 | 0 |
| 49 | है into 0.95 into 0.96 into 0.97 गर्दा | है into 0.95 into 0.96 into 0.97 गर्दा | 40.00 → 40.00 | 0 |
| 50 | Sonu plus के त Manu है Sonu plus Manu ले के गर्छन् 15 दिनमा है | Sonu plus के त Manu है Sonu plus Manu ले के गर्छन् 15 दिनमा है | 42.86 → 42.86 | 0 |

## Notes on changed references

- Item 7 (`test/TftKf_L-qBA/155184-164144`): Corrected the reference after listening. Aayush and Simran are person names.
- Item 26 (`test/bZFcrpg-tlo/500784-509872`): No correction note recorded.
- Item 30 (`test/sGhq22Tx5ew/2032592-2043536`): for some reason का मुनि was being recognozed as -
- Item 34 (`test/zYLanqYoX24/391216-399936`): No correction note recorded.
- Item 36 (`test/P9dy-ECijcI/3381072-3389136`): one nepali words was missing so i added it
- Item 39 (`test/P9dy-ECijcI/1263200-1272256`): No correction note recorded.
- Item 42 (`test/HQJoP3X6UdY/596848-605408`): No correction note recorded.
- Item 44 (`test/yTZL86j1yRE/440208-453184`): No correction note recorded.

## Limits and reproduction

This is a balanced 10-per-published-CMI-band diagnostic audit across 18 videos and two source channels, not a random population sample. One researcher reviewed script-suggested tags; the assistant did not independently listen. The corrected references are operational references for sensitivity analysis, not an independent gold standard. Do not extrapolate the edited-clip fraction to the entire dataset.

Compare these 50-clips scores only with each other. The 1,198-clip overall scores use a different population and remain unchanged. This analysis does not establish a CMI effect, statistical significance, a causal hosting effect or a general model ranking. Predeclared uncertainty/CMI analyses and report preparation remain outstanding.

Original refs: `data/manifests/reference_audit_20261105_selection.json`. Human refs: `data/annotations/reference_audit_20261112_frozen.json`. Source dataset: `saileshbro/nepali-cs-asr`, pinned revision `dd00ca41dd38774cd6097c372c16939d7f3746df`, CC BY-NC 4.0 as recorded in the pinned dataset card. No source audio is copied into this report.

```powershell
.\.venv\Scripts\python.exe src/compare_audited_references.py
```

The JSON result contains per-clip identities, text/version scores, edit counts, raw sensitivity, CMI changes and source checksums. Re-running uses saved outputs and adds no transcription requests.
