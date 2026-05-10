# Water Quality Smoke Dataset

Small EPA-style fixture for proving DataRoot is not hardcoded to the lab
demo domains.

```powershell
python -m dataroot.cli profile ExampleData/water_quality/raw
python -m dataroot.cli link
python -m dataroot.cli ask "Which stations exceeded nitrate limits in 2024?"
```
