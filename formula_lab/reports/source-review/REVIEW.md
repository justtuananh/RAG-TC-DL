# Source review — 2026-09-28

Technical review by Codex, NOT approval by a metrology specialist. Originals in TC_DL remain unchanged. Six calculators are a deliberately bounded pilot; this is not verification of all 351 math objects.

Method: inspect original DOCX XML and render originals with LibreOffice; inspect PNG pages. Compare equations, surrounding variable definitions, unit and applicability prose against candidate snippets. Images are included here for independent review. Render page numbers differ from printed page numbers.

| Calculator | Original evidence | Checked equation |
|---|---|---|
| valve | 1.061 rendered page 12 / printed page 9 | Delta P_cd = P_m - P_cd; all Pa |
| volume | 1.063 original OMML, section 5.2; context rendered page 8 | V_pl = 500 - V_đ, mL; initial inspection, 500 mL cylinder |
| rotation | 1.071 rendered page 8 | tau = tau_t * eta_t / eta; delta temperature > 3 C; 140 bar and initial angular speed conditions |
| fall | 1.071 rendered page 9 | V = V_t * eta_t / eta; delta temperature > 2 C; 700 bar; V_t entered as mean of 3 readings |
| gravity | 1.071 rendered pages 10–11 | P = P_0 * g_d / g_0; distinct local/calibration gravity |
| error | 1.071 rendered pages 10–11 | Delta_1=P-P_c1; Delta_2=P-P_c2; Delta=(Delta_1+Delta_2)/2; delta=Delta/P*100 |

Findings:
- 1.071 extraction contains duplicated symbols from coexisting OMML/MathType; definitions must be matched to source layout, not token order in Markdown.
- LibreOffice rendering omits the native OMML equation for 1.063, while its DOCX XML explicitly contains subscript V/pl, literal '=500-', subscript V/đ. Formula verified from that original structured XML, not the blank PDF rendering.
- Rendered equations for 1.071 time/speed agree with OLE extraction. The original contains stray MERGEFORMAT field text; it is not an arithmetic operand.
- Domain limits >=0 for physical inputs, positive divisors and max 500 mL are pilot input policies, not claimed as all operating limits specified by the source.
- Upper/lower pass/fail limits in the documents are NOT implemented; the calculator returns numeric results only.
- Applied conditions other than temperature are explicit user confirmations, not independently measured facts. Mis-entered but physically plausible values remain undetectable.
