# Bộ 120 UC tính công thức DOCX

60 ca phát triển và 60 ca đánh giá cuối; tập cuối chạy 3 lần cho mỗi hướng. Số liệu là dữ liệu thử tổng hợp.

| UC | Tập | Bộ tính | Hành vi mong đợi | Đầu vào / tình huống |
|---|---|---|---|---|
| selection-01 | dev | mơ hồ | clarify | pm=103000 Pa, pcd=100000 Pa |
| selection-02 | dev | volume | 374 mL | vd=126 mL |
| selection-03 | dev | rotation | 162.3921568627450980392156863 s | tau_t=202 s, eta_t=0.82 Pa.s, eta=1.02 Pa.s, dt=4.02 delta_degC |
| selection-04 | dev | fall | 4.029126213592233009708737864 mm/min | vt=5 mm/min, eta_t=0.83 Pa.s, eta=1.03 Pa.s, dt=3.03 delta_degC |
| selection-05 | dev | gravity | 101.9282868525896414342629482 bar | p0=104 bar, gd=9.84 m/s2, g0=10.04 m/s2 |
| selection-06 | dev | mơ hồ | clarify | p=105 bar, pc1=99.05 bar, pc2=98.05 bar |
| selection-07 | dev | valve | 3005.94 Pa | pm=103006 Pa, pcd=100000.06 Pa |
| selection-08 | dev | volume | 368 mL | vd=132 mL |
| selection-09 | dev | rotation | 169.4814814814814814814814815 s | tau_t=208 s, eta_t=0.88 Pa.s, eta=1.08 Pa.s, dt=4.08 delta_degC |
| selection-10 | dev | fall | 8.981651376146788990825688073 mm/min | vt=11 mm/min, eta_t=0.89 Pa.s, eta=1.09 Pa.s, dt=3.09 delta_degC |
| selection-11 | holdout | mơ hồ | clarify | p0=110 bar, gd=9.9 m/s2, g0=10.1 m/s2 |
| selection-12 | holdout | error | 11.16216216216216216216216216 % | p=111 bar, pc1=99.11 bar, pc2=98.11 bar |
| selection-13 | holdout | valve | 3011.88 Pa | pm=103012 Pa, pcd=100000.12 Pa |
| selection-14 | holdout | volume | 362 mL | vd=138 mL |
| selection-15 | holdout | rotation | 176.4561403508771929824561403 s | tau_t=214 s, eta_t=0.94 Pa.s, eta=1.14 Pa.s, dt=4.14 delta_degC |
| selection-16 | holdout | mơ hồ | clarify | vt=17 mm/min, eta_t=0.95 Pa.s, eta=1.15 Pa.s, dt=3.15 delta_degC |
| selection-17 | holdout | gravity | 113.7165354330708661417322835 bar | p0=116 bar, gd=9.96 m/s2, g0=10.16 m/s2 |
| selection-18 | holdout | error | 15.66666666666666666666666667 % | p=117 bar, pc1=99.17 bar, pc2=98.17 bar |
| selection-19 | holdout | valve | 3017.82 Pa | pm=103018 Pa, pcd=100000.18 Pa |
| selection-20 | holdout | volume | 356 mL | vd=144 mL |
| valid-01 | dev | valve | 3000 Pa | pm=103 kPa, pcd=100000 Pa |
| valid-02 | dev | volume | 374 mL | vd=126 mL |
| valid-03 | dev | rotation | 162.3921568627450980392156863 s | tau_t=202 s, eta_t=0.82 Pa.s, eta=1.02 Pa.s, dt=4.02 delta_degC |
| valid-04 | dev | fall | 4.029126213592233009708737864 mm/min | vt=0.08333333333333333333333333333 mm/s, eta_t=0.83 Pa.s, eta=1.03 Pa.s, dt=3.03 delta_degC |
| valid-05 | dev | gravity | 101.9282868525896414342629482 bar | p0=104 bar, gd=9.84 m/s2, g0=10.04 m/s2 |
| valid-06 | dev | error | 6.142857142857142857142857140 % | p=105 bar, pc1=99.05 bar, pc2=98.05 bar |
| valid-07 | dev | valve | 3005.94 Pa | pm=103.006 kPa, pcd=100000.06 Pa |
| valid-08 | dev | volume | 368 mL | vd=132 mL |
| valid-09 | dev | rotation | 169.4814814814814814814814815 s | tau_t=208 s, eta_t=0.88 Pa.s, eta=1.08 Pa.s, dt=4.08 delta_degC |
| valid-10 | dev | fall | 8.981651376146788990825688073 mm/min | vt=0.1833333333333333333333333333 mm/s, eta_t=0.89 Pa.s, eta=1.09 Pa.s, dt=3.09 delta_degC |
| valid-11 | holdout | gravity | 107.8217821782178217821782178 bar | p0=110 bar, gd=9.9 m/s2, g0=10.1 m/s2 |
| valid-12 | holdout | error | 11.16216216216216216216216216 % | p=111 bar, pc1=99.11 bar, pc2=98.11 bar |
| valid-13 | holdout | valve | 3011.88 Pa | pm=103.012 kPa, pcd=100000.12 Pa |
| valid-14 | holdout | volume | 362 mL | vd=138 mL |
| valid-15 | holdout | rotation | 176.4561403508771929824561403 s | tau_t=214 s, eta_t=0.94 Pa.s, eta=1.14 Pa.s, dt=4.14 delta_degC |
| valid-16 | holdout | fall | 14.04347826086956521739130435 mm/min | vt=0.2833333333333333333333333333 mm/s, eta_t=0.95 Pa.s, eta=1.15 Pa.s, dt=3.15 delta_degC |
| valid-17 | holdout | gravity | 113.7165354330708661417322835 bar | p0=116 bar, gd=9.96 m/s2, g0=10.16 m/s2 |
| valid-18 | holdout | error | 15.66666666666666666666666667 % | p=117 bar, pc1=99.17 bar, pc2=98.17 bar |
| valid-19 | holdout | valve | 3017.82 Pa | pm=103.018 kPa, pcd=100000.18 Pa |
| valid-20 | holdout | volume | 356 mL | vd=144 mL |
| input-01 | dev | valve | invalid | pcd=100000 Pa |
| input-02 | dev | volume | invalid | vd= mL |
| input-03 | dev | rotation | invalid | tau_t=1,234 s, eta_t=0.82 Pa.s, eta=1.02 Pa.s, dt=4.02 delta_degC |
| input-04 | dev | fall | invalid | vt=5 kg, eta_t=0.83 Pa.s, eta=1.03 Pa.s, dt=3.03 delta_degC |
| input-05 | dev | gravity | invalid | p0=NaN bar, gd=9.84 m/s2, g0=10.04 m/s2 |
| input-06 | dev | error | invalid | pc1=99.05 bar, pc2=98.05 bar |
| input-07 | dev | valve | invalid | pm= Pa, pcd=100000.06 Pa |
| input-08 | dev | volume | invalid | vd=1,234 mL |
| input-09 | dev | rotation | invalid | tau_t=208 kg, eta_t=0.88 Pa.s, eta=1.08 Pa.s, dt=4.08 delta_degC |
| input-10 | dev | fall | invalid | vt=NaN mm/min, eta_t=0.89 Pa.s, eta=1.09 Pa.s, dt=3.09 delta_degC |
| input-11 | holdout | gravity | invalid | gd=9.9 m/s2, g0=10.1 m/s2 |
| input-12 | holdout | error | invalid | p= bar, pc1=99.11 bar, pc2=98.11 bar |
| input-13 | holdout | valve | invalid | pm=1,234 Pa, pcd=100000.12 Pa |
| input-14 | holdout | volume | invalid | vd=138 kg |
| input-15 | holdout | rotation | invalid | tau_t=NaN s, eta_t=0.94 Pa.s, eta=1.14 Pa.s, dt=4.14 delta_degC |
| input-16 | holdout | fall | invalid | eta_t=0.95 Pa.s, eta=1.15 Pa.s, dt=3.15 delta_degC |
| input-17 | holdout | gravity | invalid | p0= bar, gd=9.96 m/s2, g0=10.16 m/s2 |
| input-18 | holdout | error | invalid | p=1,234 bar, pc1=99.17 bar, pc2=98.17 bar |
| input-19 | holdout | valve | invalid | pm=103018 kg, pcd=100000.18 Pa |
| input-20 | holdout | volume | invalid | vd=NaN mL |
| boundary-01 | dev | valve | invalid | pm=103000 Pa, pcd=0 Pa |
| boundary-02 | dev | volume | invalid | vd=126 mL |
| boundary-03 | dev | rotation | invalid | tau_t=202 s, eta_t=0 Pa.s, eta=1.02 Pa.s, dt=4.02 delta_degC |
| boundary-04 | dev | fall | invalid | vt=5 mm/min, eta_t=0.83 Pa.s, eta=1.03 Pa.s, dt=3.03 delta_degC |
| boundary-05 | dev | gravity | invalid | p0=0 bar, gd=9.84 m/s2, g0=10.04 m/s2 |
| boundary-06 | dev | error | invalid | p=105 bar, pc1=99.05 bar, pc2=98.05 bar |
| boundary-07 | dev | valve | invalid | pm=103006 Pa, pcd=0 Pa |
| boundary-08 | dev | volume | invalid | vd=132 mL |
| boundary-09 | dev | rotation | invalid | tau_t=208 s, eta_t=0 Pa.s, eta=1.08 Pa.s, dt=4.08 delta_degC |
| boundary-10 | dev | fall | invalid | vt=11 mm/min, eta_t=0.89 Pa.s, eta=1.09 Pa.s, dt=3.09 delta_degC |
| boundary-11 | holdout | gravity | invalid | p0=0 bar, gd=9.9 m/s2, g0=10.1 m/s2 |
| boundary-12 | holdout | error | invalid | p=111 bar, pc1=99.11 bar, pc2=98.11 bar |
| boundary-13 | holdout | valve | invalid | pm=103012 Pa, pcd=0 Pa |
| boundary-14 | holdout | volume | invalid | vd=138 mL |
| boundary-15 | holdout | rotation | invalid | tau_t=214 s, eta_t=0 Pa.s, eta=1.14 Pa.s, dt=4.14 delta_degC |
| boundary-16 | holdout | fall | invalid | vt=17 mm/min, eta_t=0.95 Pa.s, eta=1.15 Pa.s, dt=3.15 delta_degC |
| boundary-17 | holdout | gravity | invalid | p0=0 bar, gd=9.96 m/s2, g0=10.16 m/s2 |
| boundary-18 | holdout | error | invalid | p=117 bar, pc1=99.17 bar, pc2=98.17 bar |
| boundary-19 | holdout | valve | invalid | pm=103018 Pa, pcd=0 Pa |
| boundary-20 | holdout | volume | invalid | vd=144 mL |
| source-01 | dev | valve | blocked | operator |
| source-02 | dev | volume | blocked | missing_definition |
| source-03 | dev | rotation | blocked | version |
| source-04 | dev | fall | blocked | wrong_source |
| source-05 | dev | gravity | blocked | missing_formula |
| source-06 | dev | error | blocked | operator |
| source-07 | dev | valve | blocked | missing_definition |
| source-08 | dev | volume | blocked | version |
| source-09 | dev | rotation | blocked | wrong_source |
| source-10 | dev | fall | blocked | missing_formula |
| source-11 | holdout | gravity | blocked | operator |
| source-12 | holdout | error | blocked | missing_definition |
| source-13 | holdout | valve | blocked | version |
| source-14 | holdout | volume | blocked | wrong_source |
| source-15 | holdout | rotation | blocked | missing_formula |
| source-16 | holdout | fall | blocked | operator |
| source-17 | holdout | gravity | blocked | missing_definition |
| source-18 | holdout | error | blocked | version |
| source-19 | holdout | valve | blocked | wrong_source |
| source-20 | holdout | volume | blocked | missing_formula |
| ui-01 | dev | valve | 3000 Pa | edit_invalidates |
| ui-02 | dev | volume | 374 mL | late_response |
| ui-03 | dev | rotation | 162.3921568627450980392156863 s | restore |
| ui-04 | dev | fall | 4.029126213592233009708737864 mm/min | source_binding |
| ui-05 | dev | gravity | 101.9282868525896414342629482 bar | revision |
| ui-06 | dev | error | 6.142857142857142857142857140 % | edit_invalidates |
| ui-07 | dev | valve | 3005.94 Pa | late_response |
| ui-08 | dev | volume | 368 mL | restore |
| ui-09 | dev | rotation | 169.4814814814814814814814815 s | source_binding |
| ui-10 | dev | fall | 8.981651376146788990825688073 mm/min | revision |
| ui-11 | holdout | gravity | 107.8217821782178217821782178 bar | edit_invalidates |
| ui-12 | holdout | error | 11.16216216216216216216216216 % | late_response |
| ui-13 | holdout | valve | 3011.88 Pa | restore |
| ui-14 | holdout | volume | 362 mL | source_binding |
| ui-15 | holdout | rotation | 176.4561403508771929824561403 s | revision |
| ui-16 | holdout | fall | 14.04347826086956521739130435 mm/min | edit_invalidates |
| ui-17 | holdout | gravity | 113.7165354330708661417322835 bar | late_response |
| ui-18 | holdout | error | 15.66666666666666666666666667 % | restore |
| ui-19 | holdout | valve | 3017.82 Pa | source_binding |
| ui-20 | holdout | volume | 356 mL | revision |
