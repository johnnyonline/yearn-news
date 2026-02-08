# ============================================================
# THE BLUE PILL - WEEKLY NEWSLETTER CONTENT
# ============================================================
# Edit the text below to customize each section.
# Variables like {week}, {year}, {tvl}, etc. are auto-filled.
# ============================================================

# ------------------------------------------------------------
# OVERVIEW
# ------------------------------------------------------------
OVERVIEW = """
Welcome to **The Blue Pill** - *Week {week}, {year}*. A weekly update covering what's been happening across the Yearn ecosystem.

This newsletter is meant to be a simple summary of recent activity: governance discussions, vault performance, a few protocol-level metrics, and once in a while some alpha we can share. We hope you'll find it useful!

Time seems to be moving faster than ever, but work at Yearn continues steadily. Our agenda for today:
- **Yearn at a glance** - high-level protocol metrics, including TVL and week-over-week changes
- **Vaults** - top yields across chains
- **Strategy Changes** - any recent `StrategyChanged` events from indexed chains
- **yCRV** - this week's fees and week-over-week changes
- **yYB** - this week's fees and week-over-week changes
- **Alpha Corner** - features and strategies in development
"""

# ------------------------------------------------------------
# VAULTS (optional intro text before the vault list)
# ------------------------------------------------------------
VAULTS = """
"""

# ------------------------------------------------------------
# yCRV
# ------------------------------------------------------------
YCRV = """
This week yCRV stakers received **{rewards} crvUSD** rewards, compared to **{prev_rewards} crvUSD** in the prior week, for a week-over-week change of **{wow}%**
"""

# ------------------------------------------------------------
# yYB
# ------------------------------------------------------------
YYB = """
This week yYB stakers received **{rewards} crvUSD** rewards, compared to **{prev_rewards} crvUSD** in the prior week, for a week-over-week change of **{wow}%**
"""

# ------------------------------------------------------------
# ALPHA CORNER
# ------------------------------------------------------------
ALPHA = """
No Alpha today. Come back next week!
"""

# ------------------------------------------------------------
# DISCLAIMER
# ------------------------------------------------------------
DISCLAIMER = """
All data presented in this newsletter is based on publicly available sources and onchain information at the time of generation. The scripts used to collect and generate this data are open source and available [here](https://github.com/johnnyonline/yearn-news).
"""

# ------------------------------------------------------------
# SIGN OFF
# ------------------------------------------------------------
SIGN_OFF = """
---

**Until next time, peace!**
"""
