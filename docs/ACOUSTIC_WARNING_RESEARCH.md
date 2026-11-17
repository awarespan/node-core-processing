# AWARESPAN Acoustic Warning: Evidence Review and Configuration Decision

**Reviewed:** 17 November 2026
**Scope:** audible/high-frequency human response, canine hearing/response, and the current Pi speaker implementation.

## Decision

There is no scientifically established, universally effective frequency band that safely irritates humans or scares/repels dogs. The literature supports two narrower conclusions: (1) some people find high-frequency tones more unpleasant at matched subjective loudness, with large individual differences; and (2) dogs can hear high frequencies, but hearing sensitivity is not evidence that a tone will repel them. A dog-repellent experiment did not find one tested device/frequency that repelled every dog.

**Do not substitute 14–18 kHz or 20–35 kHz as an AWARESPAN deterrence band.** That would turn findings about perception or hearing into an unsupported claim about reliable deterrence, while intentionally increasing distress exposure. The Pi's 900–1100 Hz range is retained only as a generic audible alert-pitch range; it is not described as a deterrence band. The speaker is fail-closed by default until the physical speaker/amplifier is verified and its acoustic output is measured.

## Human evidence

### Kurakata, Mizunami and Matsushita (2013)

*Sensory unpleasantness of high-frequency sounds*, **Acoustical Science and Technology**, 34(1), 26–33. DOI: [10.1250/ast.34.26](https://doi.org/10.1250/ast.34.26).

The study examined pure tones and narrow-band noise at frequencies of 1 kHz and above. The authors found that unpleasantness was more dependent on sound-pressure level than on frequency, and that unpleasantness rose faster than perceived loudness as SPL increased. Pure tones were more unpleasant than equal-loudness narrow-band noise. This does not identify a frequency-only operating window that is reliably aversive across people.

### Lineton et al. (2024)

*Sensory unpleasantness of very-high frequency sound and audible ultrasound*, **The Journal of the Acoustical Society of America**, 156, 1565–1574. DOI: [10.1121/10.0028380](https://doi.org/10.1121/10.0028380).

Seventeen participants aged 18–33 rated 14, 16 and 18 kHz tones against a 1 kHz reference at matched subjective loudness levels. The higher-frequency tones were rated more unpleasant overall, but audibility differed considerably, especially at 18 kHz; the 18 kHz comparison was underpowered. Only the 14 kHz comparison in the asymptomatic group was statistically significant under the paper's corrected threshold. This is evidence of potential unpleasantness under laboratory conditions, not a recommendation or a universal human deterrent band.

The same paper reviews public exposure to pest-deterrent devices. It cites a 20 kHz device measured at 90–130 dB SPL and a separate device spanning 12.5–35 kHz at 44–71 dB SPL, with audible exposures often described as annoying or distressing. These reports reinforce the need not to use high-frequency exposure as a casual public-area deterrent.

## Canine evidence

### Blackshaw et al. (1990)

*Aversive responses of dogs to ultrasonic, sonic and flashing light units*, **Applied Animal Behaviour Science**, 25(1–2), 1–8. DOI: [10.1016/0168-1591(90)90064-K](https://doi.org/10.1016/0168-1591(90)90064-K).

The first experiment tested devices spanning approximately 7–45 kHz with outputs reported around 60–75 dB SPL. No device repelled all dogs at any tested frequency or level, though some dogs showed aversive behaviour. A second experiment tested modified outputs, including devices around 118–120 dB; some dogs reacted, but this is not an acceptable engineering target for an unattended product. The paper does not establish a universal canine deterrence band.

### Guérineau et al. (2024)

*Determining Hearing Thresholds in Dogs Using the Staircase Method*, **Veterinary Sciences**, 11(2), 67. DOI: [10.3390/vetsci11020067](https://doi.org/10.3390/vetsci11020067).

The behavioral study measured thresholds in five dogs per tested frequency at 0.5, 4 and 20 kHz. The reported mean threshold at 20 kHz was 8.5 ± 12.8 dB SPL, suggesting substantial sensitivity in at least some dogs. This establishes detectability, not fear, distress, avoidance or deterrence.

### Riemer (2023)

*Therapy and Prevention of Noise Fears in Dogs—A Review of the Current Evidence for Practitioners*, **Animals**, 13(23), 3664. DOI: [10.3390/ani13233664](https://doi.org/10.3390/ani13233664).

This review characterizes noise fear as a common canine behavioral problem and emphasizes welfare-oriented management and counterconditioning. It is not evidence for a useful dog-deterrent frequency; it supports avoiding a design whose purpose is to induce fear in dogs.

## Engineering implications for AWARESPAN

1. Keep the current 900–1100 Hz range only as a generic alert-pitch variation. Do not label it a science-backed deterrent, irritation band, dog-repellent tone, or habituation-proof signal.
2. Do not implement human-targeted 14–18 kHz tones or canine-targeted 20–45 kHz ultrasound on the basis of these papers.
3. Speaker output now defaults to disabled (`SPEAKER_ENABLED=false`, `SIREN_ENABLED=false`, `PRESENCE_DETERRENCE_ENABLED=false`). Person is the only default presence label; `dog` is filtered out by the response selector even if an operator adds it to the presence-target configuration.
4. ALSA enumeration verifies an audio interface, not the physical transducer or its acoustic output. Commissioning must verify the speaker/amplifier and measure SPL using an appropriate calibrated meter at representative listener/animal positions before any explicit enablement.
5. The code's digital amplitude (0.08 = 8% full scale) is not an acoustic SPL measurement or a safety limit.
6. Random pitch selection is a variability mechanism only. The cited studies do not show that randomizing a tone prevents habituation. Do not state that it does.

## References

- Kurakata, K., Mizunami, T., & Matsushita, K. (2013). [Sensory unpleasantness of high-frequency sounds](https://doi.org/10.1250/ast.34.26). *Acoustical Science and Technology*, 34(1), 26–33.
- Lineton, B., Al Balushi, R. A. R., Lloyd Jones, S., Leighton, T. G., & Fletcher, M. D. (2024). [Sensory unpleasantness of very-high frequency sound and audible ultrasound](https://doi.org/10.1121/10.0028380). *JASA*, 156, 1565–1574.
- Blackshaw, J. K., Cook, G. E., Harding, P., Day, C., Bates, W., Rose, J., & Bramham, D. (1990). [Aversive responses of dogs to ultrasonic, sonic and flashing light units](https://doi.org/10.1016/0168-1591(90)90064-K). *Applied Animal Behaviour Science*, 25(1–2), 1–8.
- Guérineau, C., Broseghini, A., Lõoke, M., Dehesh, G., Mongillo, P., & Marinelli, L. (2024). [Determining Hearing Thresholds in Dogs Using the Staircase Method](https://doi.org/10.3390/vetsci11020067). *Veterinary Sciences*, 11(2), 67.
- Riemer, S. (2023). [Therapy and Prevention of Noise Fears in Dogs—A Review of the Current Evidence for Practitioners](https://doi.org/10.3390/ani13233664). *Animals*, 13(23), 3664.
- Health Canada (1991). [Guidelines for the Safe Use of Ultrasound: Part II—Industrial & Commercial Applications, Safety Code 24](https://www.canada.ca/en/health-canada/services/environmental-workplace-health/reports-publications/radiation/guidelines-safe-use-ultrasound-part-industrial-commercial-applications-safety-code-24.html).
