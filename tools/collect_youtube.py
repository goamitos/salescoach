#!/usr/bin/env python3
"""
YouTube Transcript Collection

Extracts transcripts from sales-focused YouTube videos
for processing and categorization.

Usage:
    python tools/collect_youtube.py

Output:
    .tmp/youtube_raw.json
"""
import json
import os
import time
import logging
from datetime import datetime
from typing import Optional

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.proxies import GenericProxyConfig
from youtube_transcript_api._errors import (
    TranscriptsDisabled,
    NoTranscriptFound,
)
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from pyairtable import Api

from config import (
    TMP_DIR,
    RATE_LIMIT_YOUTUBE,
    AIRTABLE_API_KEY,
    AIRTABLE_BASE_ID,
    AIRTABLE_TABLE_NAME,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# YouTube Channels Reference — Validated via YouTube Data API v3 (2026-02-06)
# ===========================================================================
# Format: Expert Name: "Channel Name" (topic) | or "Guest appearances only"
# Channels verified by matching API channel search → uploads playlist → sales content.
#
# VERIFIED OWN CHANNELS (29 experts)
# -----------------------------------
# Ian Koniak:          "Ian Koniak Sales Coaching" (enterprise sales, discovery)
# Morgan J Ingram:     "Morgan J Ingram" / "The SDR Chronicles" (SDR, outbound)
# Daniel Disney:       "Daniel Disney" (LinkedIn selling)
# Samantha McKenna:    "Samantha McKenna - #samsales" (Show Me You Know Me)
# John Barrows:        "John Barrows" / "JBarrows Sales Training" (sales training)
# Josh Braun:          "Josh Braun" (outbound, objection handling)
# Jeb Blount:          "Sales Gravy" (sales acceleration, EQ)
# Chris Voss:          "Chris Voss & The Black Swan Group" (negotiation)
# Will Aitken:         "Will Aitken" (sales leadership, coaching)
# Devin Reed:          "Devin Reed | The Reeder" (content, copywriting)
# Florin Tatulea:      "Florin Tatulea" (LinkedIn selling, SDR)
# Kyle Coleman:        "Kyle Coleman" (messaging, GTM)
# Anthony Iannarino:   "Anthony Iannarino" (B2B sales leadership)
# Chris Orlob:         "Chris Orlob at pclub" (deal mechanics, data-driven)
# Jill Konrath:        "Jill Konrath" (SNAP selling, agile selling)
# Shari Levitin:       "Shari Levitin" (human-centered selling)
# Tiffani Bova:        "Tiffani Bova" (growth strategy, keynotes)
# Amy Volas:           "Amy Volas Avenue Talent Partners" (GTM hiring)
# Jim Keenan:          "Keenan" (Gap Selling)
# Mark Hunter:         "Mark Hunter" (prospecting, The Sales Hunter)
# Kwame Christian:     "Kwame Christian Esq., M.A." (difficult conversations)
# Mo Bunnell:          "Mo Bunnell" (business development)
# Scott Leese:         "The Scott Leese" (Surf & Sales, pipeline scaling)
# Hannah Ajikawo:      "by Hannah Ajikawo" (GTM, EMEA sales)
# Colin Specter:       "Colin Specter" (AI cold calling, Orum)
# Giulio Segantini:    "Giulio Segantini" (Underdog Sales, cold calling)
# Nick Cegelski:       "Nick Cegelski" (30MPC co-host, cold calling)
# Sarah Brazier:       "Sarah Brazier" (SDR strategy)
# Niraj Kapur:         "Neeraj Kapur" (trust building, LinkedIn)
#
# COMPANY CHANNELS (3)
# --------------------
# 30MPC:               "30 Minutes to President's Club" (cold calling, discovery)
# Gong.io:             "Gong" (revenue intelligence, data-driven sales)
# Pavilion:            No curated videos yet
#
# GUEST APPEARANCES ONLY (13 experts — no verified own channel)
# --------------------------------------------------------------
# Nate Nasralla:       Guest on 30MPC, pclub, Sales Feed (discovery, qualification)
# Armand Farrokh:      Guest on 30MPC, Pipedrive, Josh Braun (discovery, frameworks)
# Gal Aga:             Guest on Project Moneyball, Steve Pugh (Aligned, buyer enablement)
# Becc Holland:        Guest on Chili Piper, Chorus (Flip the Script, personalization)
# Jen Allen-Knuth:     Guest on Close, Heinz Marketing, Lavender (enterprise discovery)
# Belal Batrawy:       Guest on Drift, Mixmax, Sales Feed (Death to Fluff, outreach)
# Rosalyn Santa Elena: Guest on SaaStr, Salesloft, Ebsta (RevOps)
# Bryan Tucker:        Guest on Ambition (sales leadership)
# Kevin Dorsey:        Guest on Inside Sales Excellence, RevGenius, SaaStock (KD, leadership)
# Mark Kosoglow:       Guest on Emblaze, Sell Better (sales leadership)
# Maria Bross:         Guest on Sales Stories IRL, Sell Better (sales strategy)
# Jesse Gittler:       Guest on Sales Leader Forums (sales leadership)
# Julie Hansen:        Guest on Crystal Knows, Heinz Marketing (virtual selling)
#
# GUEST APPEARANCES (added via targeted search, 2026-02-07)
# ----------------------------------------------------------
# Alexandra Carter:    Negotiation expert — CNBC, Google, BigSpeak, Banking On Cultura (15 videos)
# Chantel George:      Sistas in Sales channel (@sistasinsales) — summit workshops, panels (15 videos)
# Justin Michael:      JMM/HYPCCCYCL — FunnelFLARE, Oren Klaff, RightBound, Apollo.io (7 videos)
#
# NO USABLE YOUTUBE CONTENT (3 experts)
# --------------------------------------
# Ron Kimhi:           No YouTube presence found
# Caroline Celis:      Only 1 Repvue appearance (too obscure to surface)
# Erica Franklin:      Appears in Sistas in Sales panels but not named in titles

# Target video IDs (curated list)
# Format: (video_id, influencer, channel)
TARGET_VIDEOS = [
    # =====================================================
    # TOP 12 LINKEDIN SALES VOICES (from plan.md)
    # =====================================================
    # 1. Ian Koniak - Enterprise sales, discovery (Popular videos)
    (
        "f3pTqJ9yARU",
        "Ian Koniak",
        "Ian Koniak Sales Coaching",
    ),  # FREE TRAINING: MAKE $500K-1M/YEAR
    (
        "XUkgyemEbc0",
        "Ian Koniak",
        "Ian Koniak Sales Coaching",
    ),  # How I became #1 Enterprise AE at Salesforce
    (
        "MufIRTnXz1Y",
        "Ian Koniak",
        "Ian Koniak Sales Coaching",
    ),  # How to Use Chat GPT for e-mail Prospecting
    (
        "faFJ13Mdd3E",
        "Ian Koniak",
        "Ian Koniak Sales Coaching",
    ),  # The Science of Selling: quota 42 months
    (
        "Mefkm3F3BeU",
        "Ian Koniak",
        "Ian Koniak Sales Coaching",
    ),  # How to Build an Effective Prospecting Sequence
    # 3. Morgan J Ingram - SDR, outbound, sequences
    ("q0x1g0QFcFk", "Morgan J Ingram", "The SDR Chronicles"),
    ("hTJi7pE9CVY", "Morgan J Ingram", "The SDR Chronicles"),
    # 4 & 5. Armand Farrokh & Nick Cegelski - 30MPC
    (
        "5pjUStm0pvo",
        "30MPC",
        "30 Minutes to President's Club",
    ),  # Sales Email Elimination: 5 Cold Emails
    ("XvuWnvR0Mpc", "30MPC", "30 Minutes to President's Club"),  # The $1M Negotiation
    (
        "2vivv2HeiBU",
        "30MPC",
        "30 Minutes to President's Club",
    ),  # Cold Call Masterclass: The Perfect Script
    ("r43V0YXGLhg", "30MPC", "30 Minutes to President's Club"),  # Cold Call 3v3
    ("Ag-6pB51s5o", "30MPC", "30 Minutes to President's Club"),  # Cold Email Showdown
    (
        "foeXnJ1b0UE",
        "30MPC",
        "30 Minutes to President's Club",
    ),  # The $30M Deal Sold With One Page
    ("w1_0co11VWk", "30MPC", "30 Minutes to President's Club"),  # #1 Sales Rep Demo
    (
        "f-P8e2VSUnk",
        "30MPC",
        "30 Minutes to President's Club",
    ),  # Negotiation Masterclass
    ("9WtOHUDgbIA", "30MPC", "30 Minutes to President's Club"),  # Live Cold Calls
    # 11. Samantha McKenna - #samsales, Show Me You Know Me
    ("h2872iUIXm4", "Samantha McKenna", "#samsales"),  # LinkedIn Algo Hacks
    (
        "2K3Hddd3jkw",
        "Samantha McKenna",
        "#samsales",
    ),  # Show Me You Know Me - Subject Lines
    (
        "fz9Z_4PDLOQ",
        "Samantha McKenna",
        "#samsales",
    ),  # From Cooked to Booked w/ Morgan Ingram
    ("S8g0nD-LARM", "Samantha McKenna", "#samsales"),  # Why the effort matters - SMYKM
    (
        "9XvRJagw6ZA",
        "Samantha McKenna",
        "#samsales",
    ),  # How to Break into an ENT Account
    # =====================================================
    # ADDITIONAL INFLUENCERS
    # =====================================================
    # John Barrows - JBarrows Sales Training
    ("Z5vxRC8dMvs", "John Barrows", "JBarrows Sales Training"),
    ("gOqL9-RCj94", "John Barrows", "JBarrows Sales Training"),
    # Josh Braun - Sales tips
    ("j5zRyXLvngg", "Josh Braun", "Josh Braun"),
    ("Kl2zmeHblmI", "Josh Braun", "Josh Braun"),
    # Jeb Blount - Sales Gravy
    ("n6mNxKAt9TU", "Jeb Blount", "Sales Gravy"),
    ("3y8nP8VnOp0", "Jeb Blount", "Sales Gravy"),
    # Chris Voss - Negotiation
    ("guZa7mQV1l0", "Chris Voss", "MasterClass"),
    ("llctqNJr2IU", "Chris Voss", "Big Think"),
    # Gong.io - Data-driven sales
    ("SHwGqFt3fkU", "Gong.io", "Gong"),
    ("tXrU8-S-F6U", "Gong.io", "Gong"),
    # Auto-discovered 2026-01-31
    ("K9ffRCbkrRc", "Ian Koniak", "Ian Koniak Channel"),
    ("_G-5i4HeO0Y", "Ian Koniak", "Ian Koniak Channel"),
    ("PwPriX_cmVo", "Ian Koniak", "Ian Koniak Channel"),
    ("2FRu6gXfXvM", "Ian Koniak", "Ian Koniak Channel"),
    ("inPr-Hxe_4k", "Ian Koniak", "Ian Koniak Channel"),
    ("iQKYPZE9MKk", "Ian Koniak", "Ian Koniak Channel"),
    ("FN8zG1Xm8OQ", "Ian Koniak", "Ian Koniak Channel"),
    ("US4va6fXUUo", "Ian Koniak", "Ian Koniak Channel"),
    ("e36YdbEyOb4", "Ian Koniak", "Ian Koniak Channel"),
    ("9sHMs3s-jRk", "Ian Koniak", "Ian Koniak Channel"),
    ("qxWI06O1Mr4", "Ian Koniak", "Ian Koniak Channel"),
    ("FjDfipbnd1Y", "Ian Koniak", "Ian Koniak Channel"),
    ("15pdWDG5eaw", "Ian Koniak", "Ian Koniak Channel"),
    ("uqTCYF53dUg", "Ian Koniak", "Ian Koniak Channel"),
    ("-BYCegr0tiQ", "Ian Koniak", "Ian Koniak Channel"),
    ("KNtpGkD_Mkw", "Samantha McKenna", "Samantha McKenna Channel"),
    ("AFL9_niYyok", "Samantha McKenna", "Samantha McKenna Channel"),
    ("VXg15KLlKO8", "Samantha McKenna", "Samantha McKenna Channel"),
    ("o_uDR792gKk", "Samantha McKenna", "Samantha McKenna Channel"),
    ("aQWpaLWOZIg", "Samantha McKenna", "Samantha McKenna Channel"),
    ("sqhtOhW0NbU", "Samantha McKenna", "Samantha McKenna Channel"),
    ("cDLzOXPM58k", "Samantha McKenna", "Samantha McKenna Channel"),
    ("_4ybWNKcGM4", "Samantha McKenna", "Samantha McKenna Channel"),
    ("rBNHyj0OdMg", "Samantha McKenna", "Samantha McKenna Channel"),
    ("EGi8nJgdXmA", "Samantha McKenna", "Samantha McKenna Channel"),
    ("Tr5Hs2ERej0", "Samantha McKenna", "Samantha McKenna Channel"),
    ("O7lrrp3S80c", "Samantha McKenna", "Samantha McKenna Channel"),
    ("V6MnoIYMeFE", "Samantha McKenna", "Samantha McKenna Channel"),
    ("-uP1HyZ2V80", "Samantha McKenna", "Samantha McKenna Channel"),
    ("s5Md43JBt-U", "Samantha McKenna", "Samantha McKenna Channel"),
    ("OCe4dtXlUKI", "Gong.io", "Gong.io Channel"),
    ("bVWJml2otH0", "Gong.io", "Gong.io Channel"),
    ("u2SOTGzL3xU", "Gong.io", "Gong.io Channel"),
    ("n_QMW-QD9dQ", "Gong.io", "Gong.io Channel"),
    ("tNB3pHLoaM0", "Gong.io", "Gong.io Channel"),
    ("MUMy99Ae2kE", "Gong.io", "Gong.io Channel"),
    ("s9ZaTt9gFD8", "Gong.io", "Gong.io Channel"),
    ("EcLtC5552rU", "Gong.io", "Gong.io Channel"),
    ("4en_TsXhtzY", "Gong.io", "Gong.io Channel"),
    ("zsgjOOsAlf8", "Gong.io", "Gong.io Channel"),
    ("6kzdhtglrRY", "Gong.io", "Gong.io Channel"),
    ("-Hpv3hqpG-c", "Gong.io", "Gong.io Channel"),
    ("XQGMeJf-Kmg", "Gong.io", "Gong.io Channel"),
    ("LnwiL2ymMgE", "Gong.io", "Gong.io Channel"),
    ("nL24YCoXw3Y", "Gong.io", "Gong.io Channel"),
    # =====================================================
    # AUTO-CURATED VIDEOS (YouTube Data API v3, 2026-02-06)
    # =====================================================
    # Alexandra Carter
    ("z45in7xwtVk", "Alexandra Carter", "Seth Dechtman - Keynote Speaker Expert"),  # Close Every Deal by Asking THIS QUESTION
    ("1igeDnw9rF4", "Alexandra Carter", "CNBC Events"),  # Alexandra Carter at CNBC's Your Money: The Art of Negotiation
    ("2Mw-PApyRbU", "Alexandra Carter", "BigSpeak Speakers Bureau"),  # Negotiation & Self Advocacy for Women
    ("6n34O_ZIebM", "Alexandra Carter", "CNBC Events"),  # CNBC Women & Wealth How to ask for more
    ("O6WWp7IH4eI", "Alexandra Carter", "PepTalkHer"),  # Negotiation in Times of Uncertainty
    ("tEitwtzuvyo", "Alexandra Carter", "PIX11 News"),  # Negotiate your way to success
    ("cKagoibllok", "Alexandra Carter", "CBS New York"),  # Alexandra Carter On New Book 'Ask for More'
    ("a4XOg6YqDTo", "Alexandra Carter", "Banking On Cultura"),  # Want to Negotiate Like a Pro? Start Here
    ("HtU-jpt3i_A", "Alexandra Carter", "Banking On Cultura"),  # Want to Negotiate Like a Pro? Start Here (pt 2)
    ("HiGlavlCi9o", "Alexandra Carter", "Google Play Books"),  # Ask For More: 10 Questions to Negotiate
    ("6m9M_ybKQRU", "Alexandra Carter", "SnapTale Audiobook Summaries"),  # Ask for More by Alexandra Carter: 8 Minute Summary
    ("WyZez_MtlNI", "Alexandra Carter", "5 Minute Mastermind"),  # Ask for More: 10 Questions to Negotiate Anything
    ("TUTQhKsCCA0", "Alexandra Carter", "Joan Kuhl"),  # Alexandra Carter on Negotiating Flexibility
    ("D6OwdLvggYI", "Alexandra Carter", "Carmine Gallo TV"),  # The Art of Negotiation
    ("ybMIF1Y2NV0", "Alexandra Carter", "Seth Dechtman - Keynote Speaker Expert"),  # You Can Get What You Want in Any Negotiation
    # Amy Volas
    ("51vb2QHq4mw", "Amy Volas", "Amy Volas Avenue Talent Partners"),  # Amy Volas - 2020 B2B sales predictions
    ("0FY1P5CmMng", "Amy Volas", "Amy Volas Avenue Talent Partners"),  # Hiring Your First Sales Leade
    ("vHDHOXib2cM", "Amy Volas", "Amy Volas Avenue Talent Partners"),  # How to Be a Better Salesperson Through Relationship Selling
    ("P0X93OiRto4", "Amy Volas", "Amy Volas Avenue Talent Partners"),  # The power of LinkedIn and how it can affect your job search
    ("lu1_s7rDyBg", "Amy Volas", "Amy Volas Avenue Talent Partners"),  # Sales Hacker:  Scott Barker & Jake Reni - Sales Hacker Hirin
    ("wF87TlHStbM", "Amy Volas", "Amy Volas Avenue Talent Partners"),  # Alli mckee what sales is and not
    ("BEEqLYCyD0o", "Amy Volas", "Amy Volas Avenue Talent Partners"),  # How to ace a sales interview presentation.
    ("sZjQhcH1YF0", "Amy Volas", "Daily Sales Tips"),  # Sales Tip 359: Playing the Long Game on LinkedIn - Amy Volas
    ("6obMvJI7SLg", "Amy Volas", "Insightly CRM by Unbounce"),  # Women in Sales: Closing the Gender Gap with Amy Volas
    ("vw4iQViTgBI", "Amy Volas", "Insightly CRM by Unbounce"),  # B2B Sales in 2023: Compensations Trends in a Hot Market
    ("3I92yyXawrk", "Amy Volas", "Insightly CRM by Unbounce"),  # The Secret to Reducing Sales Turnover: Your Hiring & Onb
    # Anthony Iannarino
    ("eh9W97x-JHg", "Anthony Iannarino", "Anthony Iannarino"),  # Reviving Outbound B2B Sales: Mastering Traditional Strategie
    ("17SF_CBE2Pg", "Anthony Iannarino", "Anthony Iannarino"),  # The 17 minute Cold Call Course for B2B Sales
    ("EASwmKL6HRI", "Anthony Iannarino", "Anthony Iannarino"),  # Why Success in B2B Sales Requires a Focus on the Basics of S
    ("jcRM_GXOUaY", "Anthony Iannarino", "Anthony Iannarino"),  # B2B Sales Training by Anthony Iannarino: A Preview of the Ac
    ("D_WX-FBJyZY", "Anthony Iannarino", "Anthony Iannarino"),  # AI in B2B Sales: Why the Human Still Matters
    ("dU1Cqd0B7wE", "Anthony Iannarino", "Anthony Iannarino"),  # Why 'Why Change?' Beats 'Why Us?' in Modern B2B Sales
    ("jLr4Q3wPfE4", "Anthony Iannarino", "Anthony Iannarino"),  # Win Rate Matters More Than Pipeline Size
    ("j2JSn5a3yog", "Anthony Iannarino", "Anthony Iannarino"),  # Why You're Getting Ghosted in B2B Sales. #shorts
    ("CUUbwgiGGRM", "Anthony Iannarino", "Anthony Iannarino"),  # B2B Sales Training: Deep Insight
    ("2GSeAbfk2Ug", "Anthony Iannarino", "Anthony Iannarino"),  # B2B Sales Training: The Done for You Approach
    ("kV_BuChm5no", "Anthony Iannarino", "Anthony Iannarino"),  # B2B Sales Training and Why Salespeople Fail
    ("lrVXWaNOv94", "Anthony Iannarino", "Anthony Iannarino"),  # B2B Sales and My Journey from Hair Band to Professional B2B
    ("QpoodOd4B-8", "Anthony Iannarino", "Anthony Iannarino"),  # How to Help Your B2B Sales Team Hit Aggressive Targets
    ("6ktbWi8B7b0", "Anthony Iannarino", "Anthony Iannarino"),  # 2022 Executive Briefing on B2B Sales
    ("tXP_ghG_Vuk", "Anthony Iannarino", "Anthony Iannarino"),  # The Nonlinearity of the Sales Process and the Buyer's Journe
    # Armand Farrokh
    ("0Ud8KGh5ZWo", "Armand Farrokh", "Emblaze | Revenue Community by Corporate Visions"),  # Monday Morning Sales Minute - Objection Ha
    ("0ryH7Z0dkyI", "Armand Farrokh", "30 Minutes to President's Club"),  # I Handle EVERY Cold Call Objection like Mr Miyagi
    ("9nslW2ADMyo", "Armand Farrokh", "Accord"),  # How to Build a Winning Business Case in B2B Sales
    ("DLOGxz_Wmuo", "Armand Farrokh", "Pipedrive"),  # 16 Tips for Closing More Deals
    ("Cvwha9306V4", "Armand Farrokh", "30 Minutes to President's Club"),  # Triple Your Cold Call Meetings - Steal This Proven Script
    ("DnCTiHMp9PA", "Armand Farrokh", "30 Minutes to President's Club"),  # Stop Selling For Crappy Companies (Look For THIS)
    ("-NAT1cJeQ_A", "Armand Farrokh", "30 Minutes to President's Club"),  # How I Kickoff Every Sales Call
    ("8NtaPHOxAEU", "Armand Farrokh", "Josh Braun"),  # Live Cold Call Critique - What do you do?
    ("sga6s21dJW0", "Armand Farrokh", "Jump 450"),  # How To Start The #1 Sales Podcast In The World
    ("z_JohGi_i7k", "Armand Farrokh", "30 Minutes to President's Club"),  # How I Handle "Not Interested" (Cold Call Script)
    ("xB5jHQV0FpE", "Armand Farrokh", "Josh Braun"),  # 4 Habits That Make Selling More Joyful
    ("La0ZRGE9NN8", "Armand Farrokh", "Josh Braun"),  # Visceral Cold Calls That Engage - Armand Farrokh
    ("VX-aAirPJy4", "Armand Farrokh", "SnapTale Audiobook Summaries"),  # Cold Calling Sucks (And That's Why It Works)
    ("xO8TAX0kYys", "Armand Farrokh", "Evolve With Books"),  # Cold Calling Sucks - Master Cold Calls with Armand Farrokh
    # Becc Holland
    ("iwojDBYmTY0", "Becc Holland", "Chorus by ZoomInfo"),  # The 7 Deadly Sins of Messaging (for Outbound Sales)
    ("_ghxMac2LUg", "Becc Holland", "Chorus by ZoomInfo"),  # Passing An Appointment from SDR to AE
    ("3KtlJo59vfg", "Becc Holland", "Connor Shulstad"),  # B2B sales call, MKTG4332
    ("PltwHHbWMVo", "Becc Holland", "Chili Piper"),  # How to Craft an Outbound Strategy Leading with Unknown Probl
    ("RLzYlvn0vmg", "Becc Holland", "Tenbound Now Powered by Cience"),  # Sales Development Whiteboard Wednesdays with Becc Holland
    ("7Q3X1X1Kw7s", "Becc Holland", "Chorus by ZoomInfo"),  # How to Turn Any Shallow Objection Into A Meeting
    ("2uikGuUO5Wc", "Becc Holland", "Chorus by ZoomInfo"),  # How To Handle "I'm Not The Right Person" Objection
    ("L1Ex68YHz7A", "Becc Holland", "Chorus by ZoomInfo"),  # How to Build a Prospect Friendly Qualifying Process
    ("z7Q3wFN4Cy0", "Becc Holland", "Josh Braun"),  # Becc & Braun - Objection Chat
    ("P3TP9p528mk", "Becc Holland", "Tenbound Now Powered by Cience"),  # Whiteboard Wednesdays with Becc Holland
    ("_qBaTsS2cr4", "Becc Holland", "Chorus by ZoomInfo"),  # Why AEs Shouldn't Determine if a Meeting is Qualified
    ("N5cwhSoyJGM", "Becc Holland", "Tenbound Now Powered by Cience"),  # Whiteboard Wednesday with Becc Holland
    ("S5Xx38wV3RU", "Becc Holland", "Chorus by ZoomInfo"),  # 5 Ways To Turn SDRs to AEs (Before Becoming Closers)
    ("tRaXa6cU24Y", "Becc Holland", "Chorus by ZoomInfo"),  # Seven Sequences That Nobody Is Thinking About
    # Belal Batrawy
    ("HhKcAIU2pYg", "Belal Batrawy", "Inside Sales Excellence"),  # Sell to the In-Group: Make the Prospect the Hero
    ("VvyiYKpVXGg", "Belal Batrawy", "Inside Sales Excellence"),  # Prospect Theory and Emotional Messaging
    ("I9sqaqSOUXg", "Belal Batrawy", "Sales Feed"),  # The Sales Professional's Guide to Becoming
    ("z5C-WNlzJ1Q", "Belal Batrawy", "Inside Sales Excellence"),  # Avoid No Decision By Understanding the Buyer
    ("qRkksjpPy1I", "Belal Batrawy", "Inside Sales Excellence"),  # Avoid No Decision By Understanding the Buyer
    ("rxu5J66VCxM", "Belal Batrawy", "Inside Sales Excellence"),  # The Sizzle Without the Steak: Willingness to Change
    ("eeffalHYUqY", "Belal Batrawy", "learntosell"),  # Mic Drop Cold Call Script for Podium
    ("NdIPxKIPVc0", "Belal Batrawy", "Sales Feed"),  # The BEST Cold Call Opening Lines 2025
    ("4OweikRF7bg", "Belal Batrawy", "Sales Feed"),  # Cold Calling For Beginners: A Step-by-Step Guide
    ("lQlFDr20Z30", "Belal Batrawy", "Inside Sales Excellence"),  # Developing a Mindset of Losing Less
    ("WmqF4bu46zs", "Belal Batrawy", "Inside Sales Excellence"),  # Trade Your Cleverness for Bewilderment
    ("vmm4FirCscs", "Belal Batrawy", "Inside Sales Excellence"),  # The Mic Drop Method to Frame an Inverse Outgroup
    ("37eYwN7OKaY", "Belal Batrawy", "Inside Sales Excellence"),  # Developing a Mindset of Losing Less
    ("XZRFfagFzRk", "Belal Batrawy", "Drift"),  # Belal Batrawy, Founder, DeathToFluff
    ("0_e47Ys2Fb4", "Belal Batrawy", "Mixmax"),  # Interview with Belal Batrawy, Founder of Death to Fluff
    # Bryan Tucker
    ("8L4_1tcg0o8", "Bryan Tucker", "Ambition"),  # How Gong.io is Managing Sales Teams *Right Now*
    # Chris Orlob
    ("o_0-rEyWiRY", "Chris Orlob", "Chris Orlob at pclub"),  # How to ask deal closing sales questions
    ("6pH3Sa1KJsI", "Chris Orlob", "Chris Orlob at pclub"),  # How to Run Deal-Closing Discovery With INBOUND Buyers
    ("-FEGxacgsqY", "Chris Orlob", "Chris Orlob at pclub"),  # 9 Sales Negotiation Techniques of Top SaaS Sellers
    ("yJg4KEJMF2E", "Chris Orlob", "Chris Orlob at pclub"),  # Two Sales Closing Techniques For Tech and SaaS
    ("yRhe2ryQsT8", "Chris Orlob", "Chris Orlob at pclub"),  # How to Close SaaS Deals On Time With Closing Motion
    ("clQP6x9QFFU", "Chris Orlob", "Chris Orlob at pclub"),  # Using Diagnostic Coaching to Drive AE Sales Performance
    ("zx-NmhD8uI0", "Chris Orlob", "Chris Orlob at pclub"),  # The Perfect SaaS Cold Outbound Email Framework For 2023
    ("02oGY8FNXaM", "Chris Orlob", "Chris Orlob at pclub"),  # How to Know If You Have a Deal-Closing Champion
    ("EPgeioDTWpA", "Chris Orlob", "Chris Orlob at pclub"),  # 20 Sales Cheat Codes That Made Me $1.63M in SaaS Sales
    ("3HfnncbNXhc", "Chris Orlob", "Chris Orlob at pclub"),  # Selling to the C-Suite: Better Questions Beat More Questions
    ("W-iTBdH4Ghs", "Chris Orlob", "Chris Orlob at pclub"),  # Most trainers preach SELL VALUE! I'll show you how
    ("OFVJCis5rRs", "Chris Orlob", "Chris Orlob at pclub"),  # CASE STUDY: How This AE Closed a $433,000 Deal in 90 Days
    ("CIM1Q-kVlbc", "Chris Orlob", "Chris Orlob at pclub"),  # 9 Elements of Insanely Persuasive Sales Demos That SELL
    ("Dv4ZrSsqsys", "Chris Orlob", "Chris Orlob at pclub"),  # 12 Word Script to Negotiate SaaS Deals
    ("wTATVbIIbXU", "Chris Orlob", "Chris Orlob at pclub"),  # Sales Motivation: Watch Before Every SaaS Sales Call
    # Chris Voss (new videos from Black Swan Group channel)
    ("pxNwYTXkooU", "Chris Voss", "Chris Voss & The Black Swan Group"),  # The BEST Things To Say To Close A Deal
    ("zlqCrmy6p2k", "Chris Voss", "Chris Voss & The Black Swan Group"),  # How I Get The BEST Deal In Any Negotiation
    ("Y6oHQZQzeEI", "Chris Voss", "Chris Voss & The Black Swan Group"),  # FBI Hostage Negotiator EXPLAINS How To Deal With Kidnappers
    ("3mkPEOok3os", "Chris Voss", "Chris Voss & The Black Swan Group"),  # What Makes A Great CEO?
    ("qV_d7HSrpP0", "Chris Voss", "Chris Voss & The Black Swan Group"),  # Don't Ask This Question In A Negotiation
    ("l1y1K52MzDY", "Chris Voss", "Chris Voss & The Black Swan Group"),  # How To Know If A Deal Will Be Successful
    ("UMDW7HuvKM8", "Chris Voss", "Chris Voss & The Black Swan Group"),  # You Always LOSE A Win-Win Negotiation
    ("M5SWaVHuEGM", "Chris Voss", "Chris Voss & The Black Swan Group"),  # My First FBI Negotiation Gone HORRIBLY Wrong
    ("YhxoaptRsvE", "Chris Voss", "Chris Voss & The Black Swan Group"),  # My First Negotiation With Al Qaeda!
    ("LHRAhXI617M", "Chris Voss", "Chris Voss & The Black Swan Group"),  # Can You Really Negotiate With ANYONE??
    ("PBynqAi9FaU", "Chris Voss", "Chris Voss & The Black Swan Group"),  # NEVER Compromise In A Negotiation
    ("pTguRFIJFRs", "Chris Voss", "Chris Voss & The Black Swan Group"),  # When To Walk Away From A Negotiation!
    ("bLf81MBqTJ4", "Chris Voss", "Chris Voss & The Black Swan Group"),  # The Negotiation Trick Tim Ross Uses In Ministry
    ("EptMTDy4rG0", "Chris Voss", "Chris Voss & The Black Swan Group"),  # The BIGGEST Lie You've Heard In Sales
    ("c7IMj88FCMg", "Chris Voss", "Chris Voss & The Black Swan Group"),  # How I Deal With Bullies
    # Colin Specter
    ("vyAc_Fb718s", "Colin Specter", "Colin Specter"),  # 2023 Sales Enablement: sales reps speaking the same language
    ("A2GsBG4ZZFY", "Colin Specter", "Colin Specter"),  # What's most important for sales enablement
    ("ZFZ3TWheWNE", "Colin Specter", "Colin Specter"),  # 2023 State of Sales and AI in sales
    ("gh2qt5VyV3s", "Colin Specter", "Colin Specter"),  # The Phone is back in vogue (sales shorts)
    ("MtuzDl9itvY", "Colin Specter", "Colin Specter"),  # The Future of Cold Calling - Elite Sales Training
    ("nxh2Rn81nCo", "Colin Specter", "Colin Specter"),  # How to handle 'Budgets are frozen?'
    ("bpfzOUKVI14", "Colin Specter", "Colin Specter"),  # Women dominate the leaderboard in sales organizations
    ("71PToWWiytY", "Colin Specter", "Colin Specter"),  # 2023 Sales Tech: Point Solutions vs All-in-one
    ("U2gV1cPiU58", "Colin Specter", "Colin Specter"),  # Key ingredient to successful sales teams
    ("Gfxh8A2xV0o", "Colin Specter", "Heavybit"),  # From SDR to AE: How to Turbocharge Your Career
    # Chantel George (Sistas in Sales)
    ("p6tFAfls15A", "Chantel George", "Sistas in Sales"),  # Hey SIS! Interview with Anna Robinson, Enterprise Sales
    ("xzETSTsj7JI", "Chantel George", "Sistas in Sales"),  # Jackie McKinley - U.S. Area Enterprise Sales Leader, NetApp
    ("A1ja3U3Ap20", "Chantel George", "Sistas in Sales"),  # Leadership Workshop: Divergent Strategies for Revenue
    ("Hq9ZP-fmERU", "Chantel George", "Sistas in Sales"),  # Leveraging Internal Relationships to Succeed in Sales
    ("rJRhkIY0YrE", "Chantel George", "Sistas in Sales"),  # All In Tech Sales: Understanding the Art of Tech Sales
    ("moFpYNa5Mhc", "Chantel George", "Sistas in Sales"),  # All In: Tech Sales, Understanding the Art of Tech Sales
    ("KxD31qNZ7lg", "Chantel George", "Sistas in Sales"),  # Sistas in Sales x Walmart Connect Fireside Chat
    ("ZQutGSa9sT0", "Chantel George", "Sistas in Sales"),  # Kerry Washington - Sistas in Sales Keynote 2023
    ("jqaSPxsBn1Y", "Chantel George", "Sistas in Sales"),  # Getting your Start in Sales: How to get Your Foot in the Door
    ("CRVlD1AgCBs", "Chantel George", "Sistas in Sales"),  # Delores Bennett Rochester, Cloud Infrastructure Sales
    ("vf2DrQKIRfs", "Chantel George", "Sistas in Sales"),  # SIStory: Living Legacies Executive Sales Leader Panel
    ("U3hHm3sM9Dg", "Chantel George", "Sistas in Sales"),  # Health is Wealth: Sales Professional Wellness Journey
    ("5zvOvFCyrAs", "Chantel George", "Sistas in Sales"),  # Building your Personal Brand As a New Seller
    ("Mc_a6_FbJj8", "Chantel George", "Sistas in Sales"),  # Generative AI & The Impact of the Sales Industry
    ("GXyvjJGE_SE", "Chantel George", "Sistas in Sales"),  # State of the Customer: A Leader's Perspective
    # Daniel Disney
    ("molWx_GTIfo", "Daniel Disney", "Daniel Disney"),  # FUNNY SALES MEME! WALKING BACK AFTER CLOSING A DEAL
    ("kz5v-YYEXiY", "Daniel Disney", "Daniel Disney"),  # 7 LinkedIn Social Selling Tips In 7 Minutes
    ("AOIF2J0AmzU", "Daniel Disney", "Daniel Disney"),  # How B2B Sales Training Is Changing
    ("alb6Otavsgc", "Daniel Disney", "Daniel Disney"),  # Social Selling Show: How To Deal With HATERS
    ("ad5ZdbkBayA", "Daniel Disney", "Daniel Disney"),  # Social Selling Show: Finding Sales Insights
    ("DS5RkENG1uE", "Daniel Disney", "Daniel Disney"),  # Social Selling Show: How To Get The MOST Out Of LinkedIn
    ("Ytfv-g0eMdc", "Daniel Disney", "Daniel Disney"),  # LIVE AMA - LinkedIn Social Selling Sales
    ("lgjyE464NGU", "Daniel Disney", "Daniel Disney"),  # From ZERO to HERO in Social Selling
    ("zbrPZb1Wuxg", "Daniel Disney", "Daniel Disney"),  # How CEOs Turn LinkedIn Into an Inbound Lead Machine
    ("RvuK0w6uBEo", "Daniel Disney", "Daniel Disney"),  # Why Every CEO Should Be On LinkedIn
    ("bLZETdn_vSM", "Daniel Disney", "Daniel Disney"),  # This LinkedIn Message Closed a 1M Deal
    ("Nsypouk_kUU", "Daniel Disney", "Daniel Disney"),  # AI Won't Replace Human Selling on LinkedIn
    ("63w8N7fONFk", "Daniel Disney", "Daniel Disney"),  # LinkedIn Is NOT a Direct Selling Tool
    ("ysvMEEGaRKs", "Daniel Disney", "Daniel Disney"),  # Why Most LinkedIn Sales Advice Is Wrong
    ("z-KBeqMZBtc", "Daniel Disney", "Daniel Disney"),  # How To Find The BEST Sales Insights To Close More Deals
    # Devin Reed
    ("yAtHtlOK9XM", "Devin Reed", "Devin Reed | The Reeder"),  # B2B Creator Playbook For FREE
    ("qp1tYQeNx9w", "Devin Reed", "Devin Reed | The Reeder"),  # Don't Sell Products, Sell DIFFERENT
    ("oj0FfP6ZBlo", "Devin Reed", "Devin Reed | The Reeder"),  # Impossible To Replace The Highs From Selling
    ("iG4bXiXLDP4", "Devin Reed", "Devin Reed | The Reeder"),  # How To Master Cold Email & Content Strategy
    ("pQP4MJQ6oig", "Devin Reed", "Devin Reed | The Reeder"),  # CEO Valuable Thinking for Business Growth
    ("NEKOFx_oEbk", "Devin Reed", "Devin Reed | The Reeder"),  # Conversation That Sparked Creating And Selling
    ("xP404n_8T7g", "Devin Reed", "Devin Reed | The Reeder"),  # Storytelling Secrets To Close Deals
    ("lUI_XsuR39o", "Devin Reed", "Devin Reed | The Reeder"),  # How I Create Provocative Bold Messaging
    ("5NR1z5SQMj0", "Devin Reed", "Devin Reed | The Reeder"),  # The Secret to Solving Problems Like a Champion
    ("8ae-XWrEHkM", "Devin Reed", "Devin Reed | The Reeder"),  # First TV Show Gig Was Selling Power Tools
    ("5DOdtKR_FtE", "Devin Reed", "Devin Reed | The Reeder"),  # My First Brand Deal Paid 5 Figures!
    ("chXGJnQWHw8", "Devin Reed", "Devin Reed | The Reeder"),  # Selling My Soul To Make The Sale In Business
    ("ZPiL-iEnIok", "Devin Reed", "Devin Reed | The Reeder"),  # Giving Everything Away For FREE!
    ("npif3-jsZAw", "Devin Reed", "Devin Reed | The Reeder"),  # Put Creators FIRST In B2B Influencer Marketing
    ("bGUaqbCQzbQ", "Devin Reed", "Devin Reed | The Reeder"),  # Launching His B2B Agency
    # Florin Tatulea
    ("Ckbi1TDMlTA", "Florin Tatulea", "Florin Tatulea"),  # How To Export Sales Navigator Leads To CSV
    ("aaFjjDBBEzk", "Florin Tatulea", "Chris Orlob at pclub"),  # Cold Email Secrets from Outbound Expert Florin Tatulea
    ("lWsmoVoLDno", "Florin Tatulea", "Mailshake"),  # Leading a Successful Sales Team - Florin Tatulea
    ("AbJ3qspYBM0", "Florin Tatulea", "Mailshake"),  # Leading a Successful Sales Team - Florin Tatulea
    ("eIREmyKcdUQ", "Florin Tatulea", "Mixmax"),  # Interview with Director of Sales Florin Tatulea
    ("wZM6Ak37vjE", "Florin Tatulea", "Elric Legloire"),  # Land Your Dream SDR Job: The Strategy You Need
    ("wr80cPORfYc", "Florin Tatulea", "Sell Better"),  # 5 MIN Challenge: Re-Write a GREAT Cold Email
    ("8Fo8nsfNZxQ", "Florin Tatulea", "Woodpecker.co"),  # How to master cold email in 6 minutes
    ("2emA2W5vblA", "Florin Tatulea", "Full Audiobook"),  # Sales Success Stories: 60 Stories from 20 Top 1% Sales Pros
    ("ihQsFSsTMZs", "Florin Tatulea", "Free Audiobook"),  # Sales Success Stories: 60 Stories from 20 Top 1% Sales Pros
    ("KNGpuWN5zQE", "Florin Tatulea", "Sales Feed"),  # Cold Calling Strategy to Book More Meetings
    # Gal Aga
    ("S5aGQtdc1RE", "Gal Aga", "Project Moneyball"),  # Gal Aga CEO of Aligned - What Is Enablement
    ("8TxbBik48dY", "Gal Aga", "Steve Pugh"),  # The SaaS sales methodology
    # Giulio Segantini
    ("3gvrjBFOnZw", "Giulio Segantini", "Nazim Agabekov"),  # How I Helped Giulio Segantini Increase Sales by 300%
    ("K8m3u_LfZFA", "Giulio Segantini", "The Jason Marc Campbell Podcast"),  # How To Start A Cold Call
    ("rrgIHKGDJVg", "Giulio Segantini", "The Jason Marc Campbell Podcast"),  # Watch This 10 Minutes If You Are In Sales
    ("mr_tmkTY8IY", "Giulio Segantini", "Predictable Revenue"),  # What is the Right Way to Open Up a Cold Call?
    ("WXEX2_3Is3s", "Giulio Segantini", "ManyMangoes"),  # Master Cold Calling For Underdogs
    ("8g6r7eP6y-Y", "Giulio Segantini", "TripleSession"),  # What's the Real Reason Behind Giulio's Cold Calling
    ("8Sq1tOLuOi4", "Giulio Segantini", "Trellus"),  # Debrief with Giulio Segantini
    ("sFqnX7SzgGk", "Giulio Segantini", "Sales Feed"),  # The ONLY Cold Calling Tutorial You'll Ever Need
    # Hannah Ajikawo
    ("VGY2lfQv_Ss", "Hannah Ajikawo", "by Hannah Ajikawo"),  # How To Build High Quality Sales Pipeline
    ("jLjxLfidRsg", "Hannah Ajikawo", "by Hannah Ajikawo"),  # B2B Sales Pipeline Masterclass
    ("qF1VoaSQMks", "Hannah Ajikawo", "by Hannah Ajikawo"),  # Understanding the B2B Buyer: Insights that Shape GTM
    ("NsrKZRiVfZA", "Hannah Ajikawo", "by Hannah Ajikawo"),  # 3 Simple Tricks To Increasing Your Sales Pipeline
    ("ThAHsjA3ftk", "Hannah Ajikawo", "by Hannah Ajikawo"),  # 3 Things To Reduce Customer Churn
    ("I0__U9LGrpY", "Hannah Ajikawo", "by Hannah Ajikawo"),  # Rethinking Sales Reps Roles in B2B Sales
    ("YM72vSFEm2U", "Hannah Ajikawo", "by Hannah Ajikawo"),  # 5 Things That Will Grow Your Customer Revenue
    ("RkUgqvYUGVo", "Hannah Ajikawo", "by Hannah Ajikawo"),  # B2B Buyer Journey: How To Improve The Adoption Stage
    ("9hAtf21mP00", "Hannah Ajikawo", "by Hannah Ajikawo"),  # How To Align Revenue Team To Awareness Stage
    ("hrm74a8BX2M", "Hannah Ajikawo", "by Hannah Ajikawo"),  # Revenue Team Alignment Is Key To Sustainable Sales Growth
    ("3jmwzzWUxYg", "Hannah Ajikawo", "Mixmax"),  # Interview with Hannah Ajikawo, CEO Revenue Funnel
    ("7UmGN-TNPsM", "Hannah Ajikawo", "by Hannah Ajikawo"),  # Symbiotic Sales - The Future of Sales is Here
    ("swPC7Gu1Ktc", "Hannah Ajikawo", "by Hannah Ajikawo"),  # Hannah Ajikawo's Inspiring SaaS SKO Keynote
    ("1aRKVQ_Mo3M", "Hannah Ajikawo", "by Hannah Ajikawo"),  # Why Prospects Ghost You After Great Sales Calls
    ("HSn8vOo0to8", "Hannah Ajikawo", "by Hannah Ajikawo"),  # What No One Tells You About B2B Consulting
    # Ian Koniak (new videos)
    ("6EvD-v9wkn8", "Ian Koniak", "Ian Koniak Sales Coaching"),  # Enterprise Account Executive @ Adobe
    ("uCJx-hrsQR0", "Ian Koniak", "Ian Koniak Sales Coaching"),  # Ask Ian GPT: 24/7 Coaching for SaaS Sellers
    ("3Abv6uMaou8", "Ian Koniak", "Ian Koniak Sales Coaching"),  # Selling Is Helping: 4 Levels of Impact to Close More Deals
    ("voHyTd7GJK8", "Ian Koniak", "Ian Koniak Sales Coaching"),  # The Truth About Enterprise Sales
    ("gDYHNhk-gOM", "Ian Koniak", "Ian Koniak Sales Coaching"),  # The Proposal Template that helped me close $100M
    ("5QgtcZrFilc", "Ian Koniak", "Ian Koniak Sales Coaching"),  # Outward Selling: The Sales Approach That Works
    ("4_nNabWIDb8", "Ian Koniak", "Ian Koniak Sales Coaching"),  # Enterprise AE @ Databricks - Client Testimonial
    ("LDJLdK3VyW8", "Ian Koniak", "Ian Koniak Sales Coaching"),  # Enterprise AE @ Gong - Client Testimonial
    ("llkVkn_RHHc", "Ian Koniak", "Ian Koniak Sales Coaching"),  # Senior Enterprise AE @ Mambu - Client Testimonial
    ("cbaKYn-t7ZQ", "Ian Koniak", "Ian Koniak Sales Coaching"),  # Create the Perfect Sales Pitch using the 5 P's
    ("ycDRpN8wN3Y", "Ian Koniak", "Ian Koniak Sales Coaching"),  # Be the Buyer, not the Seller
    ("rqWsKS7e-o4", "Ian Koniak", "Ian Koniak Sales Coaching"),  # #1 Key to Winning Deals: Be the Buyer, not the Seller
    # Jeb Blount (new videos)
    ("R8zDSgiW6I4", "Jeb Blount", "Sales Gravy"),  # Fanatical Prospecting: The Brutal Truth About Sales Success
    ("LYXmf0V1FLk", "Jeb Blount", "7 Figure Squad"),  # GAME-CHANGING Sales Strategies for a FULL Pipeline
    ("fqDiCZS-tpo", "Jeb Blount", "Sales Gravy"),  # Sales Call Reluctance: Rebuilding Your Prospecting Confidence
    ("v64DAlH8NCo", "Jeb Blount", "Sales Gravy"),  # One Salesperson, $300K Revenue
    ("a58ULtqf4s8", "Jeb Blount", "Jeff Shore Real Estate Sales Training"),  # Jeb Blount's Playbook for Sales Success
    ("J7dOBVvYHCs", "Jeb Blount", "Sales Gravy"),  # How to Be Successful in Sales? 3 Non-Negotiables
    ("NFqBpmOvte0", "Jeb Blount", "Sales Gravy"),  # Maintaining Sales Momentum Through the Holidays
    ("zCN1ciXHdh4", "Jeb Blount", "Sales Gravy"),  # Overcome Sales Rejection by Finding Your Carrot
    ("8KeF3Xt7p1E", "Jeb Blount", "Sales Gravy"),  # Building Consistent Prospecting Habits
    ("ON37QYTh4Cs", "Jeb Blount", "Sales Gravy"),  # 3 Non-Negotiables for Modern Sales Success
    # Jen Allen-Knuth
    ("TqnwZxqLdEg", "Jen Allen-Knuth", "Heinz Marketing"),  # Sales Pipeline Radio - Jen Allen-Knuth
    ("Tss-AZgd9Cg", "Jen Allen-Knuth", "Lavender"),  # Which Sales Influencer Can Write The Best Cold Email?
    ("ZyI87JEoDhg", "Jen Allen-Knuth", "Close"),  # Will vs. Jen: Who can write the better inbound email
    ("vvwENiAWtLM", "Jen Allen-Knuth", "Ecosystems"),  # Challenging Customer Assumptions with Cost of Inaction
    ("6iemMb56soI", "Jen Allen-Knuth", "Mailshake"),  # COI in Cold Email - Jen Allen-Knuth
    ("8v2I_dax0Q0", "Jen Allen-Knuth", "Mailshake"),  # Cost of Inaction in Cold Email
    ("1CTnbjDelD8", "Jen Allen-Knuth", "Lavender"),  # Sales Horror Stories - Jen vs. Will Halloween Special
    ("l0x9kwDFF2I", "Jen Allen-Knuth", "Close"),  # Will vs. Jen: Who's the better sales coach?
    ("rbqMozfJkqg", "Jen Allen-Knuth", "Sales Feed"),  # Why Your Sales Emails Get Ignored
    ("TYbDZlHCDqw", "Jen Allen-Knuth", "Sales Players"),  # 20 Sales Plays I Run When Nothing Else Is Working
    ("OBObvYd7HXc", "Jen Allen-Knuth", "Sales Players"),  # 20 Sales Plays I Run When Nothing Else Is Working
    ("IsBJI0_4prU", "Jen Allen-Knuth", "RevPartners"),  # Evangelism, The Next Frontier For Growth
    # Jesse Gittler
    ("JICP4nOtx50", "Jesse Gittler", "Tony Clyde Official"),  # How to Transition from Salesperson to Manager
    ("6vAewD2LEo0", "Jesse Gittler", "Sales Leader Forums"),  # Transitioning from salesperson to manager
    # Kevin "KD" Dorsey
    ("FcK0Q9s8Wh0", "Kevin Dorsey", "Tech Journey with The Warthens"),  # How YOU SUCCEED as a BDR/SDR
    ("f12z0SfNR9U", "Kevin Dorsey", "Inside Sales Excellence"),  # Set Yourself Up for Success in Closing Through Discovery
    ("JVdB2Zl3--w", "Kevin Dorsey", "Tech Journey with The Warthens"),  # BEST Interview Tips - SaaS Sales Development
    ("ywddVzglGG0", "Kevin Dorsey", "SaaStock"),  # The Great Debate: AI in Sales
    ("7Tm2blzPyHA", "Kevin Dorsey", "CoRecruit (formerly Quil)"),  # Lessons Learned as a Sales Leader
    ("mKhcPYAEPYM", "Kevin Dorsey", "Insightly CRM by Unbounce"),  # The 10 Commandments of Daily Sales Success
    ("7avhPtcj4aA", "Kevin Dorsey", "Mailshake"),  # Loss of Skills in SaaS
    ("NhHfYp3IoRs", "Kevin Dorsey", "RevGenius"),  # Think About What WON'T Change to Predict the Future
    ("EAiIhQkTWAc", "Kevin Dorsey", "Ambition"),  # Sales Influencer Series: Kevin Dorsey
    ("eSMWeOXedms", "Kevin Dorsey", "RevGenius"),  # Adapt and Change to the Future with AI
    ("TbGkiNzgJoQ", "Kevin Dorsey", "Inside Sales Excellence"),  # Tactics for Problem-Based Discovery
    ("kLg_wlmmsU4", "Kevin Dorsey", "Anirudh Ram"),  # Walk the talk ft. Kevin 'KD' Dorsey (SVP of Sales, Bench)
    ("qRBvVlG0vhU", "Kevin Dorsey", "Inside Sales Excellence"),  # Deals are Won Through Problem-Based Discovery
    ("9ViMDJfxRq0", "Kevin Dorsey", "Sales Feed"),  # Full Cycle Sales, Proposals, and Side Hustles
    ("i_oD6AfraaM", "Kevin Dorsey", "Calendly"),  # How to Run Sales Meetings That Convert
    # Jill Konrath
    ("pJxe_v86efI", "Jill Konrath", "Jill Konrath"),  # Sales Prospecting: How to Get More Prospects
    ("FMJHG_8nhKo", "Jill Konrath", "Jill Konrath"),  # Sales Productivity: Important Research on Email
    ("8PbSrkK51JY", "Jill Konrath", "Jill Konrath"),  # Why Inbound Marketing is Vital to My Sales Success
    ("HJFhJF9TX4U", "Jill Konrath", "Jill Konrath"),  # How to Know if Your Prospecting Email is Effective
    ("J7PwgNdwcEE", "Jill Konrath", "Jill Konrath"),  # Is Your Prospecting Email Spam -- or Not?
    ("urNEX6lfZ48", "Jill Konrath", "Jill Konrath"),  # Dealing With the 'Current Vendor' Sales Objection
    ("EUqzpoeb6pQ", "Jill Konrath", "Jill Konrath"),  # Why Your Biggest Sales Opportunities Won't Close
    ("ociYUqzORqw", "Jill Konrath", "Jill Konrath"),  # The Ultimate Sales Pitch
    ("5cSXt9wkNLE", "Jill Konrath", "Jill Konrath"),  # 2 Ways to Use LinkedIn Search to Find Prospects
    ("1vJ8-2RfAN4", "Jill Konrath", "Jill Konrath"),  # Why You Don't Need Sales Closing Techniques
    ("jGLxaPIzc2E", "Jill Konrath", "Jill Konrath"),  # Start Small to Close Sales Faster
    ("PVl_Fxal2mc", "Jill Konrath", "Jill Konrath"),  # Sales Objection: Dealing with the Budget
    ("eJWtOOcoysA", "Jill Konrath", "Jill Konrath"),  # #1 Sales Meeting Follow-Up Best Practice
    ("MYTDPKFbuOw", "Jill Konrath", "Jill Konrath"),  # Sales Integrity: Being Willing to NOT Sell Something
    ("RioDKIbJ_KU", "Jill Konrath", "Jill Konrath"),  # Sales Coaching Marathon
    # Jim Keenan
    ("fo3BVAbX7e4", "Jim Keenan", "Roland Toth"),  # Gap Selling: Getting the Customer to Yes
    ("pklGXJ0Q1wQ", "Jim Keenan", "Audiobooks Summary"),  # Gap Selling: Getting the Customer to Yes
    ("DxfTCgrmRmw", "Jim Keenan", "Keenan"),  # A Lesson in Pricing for Sales People
    ("1Drso1jAoWQ", "Jim Keenan", "Keenan"),  # Most POWERFUL Sales Discovery Process
    ("lrGQkCol8Gw", "Jim Keenan", "Keenan"),  # Buyer-Centric Discovery
    ("XF19qAJ41Nk", "Jim Keenan", "Keenan"),  # Selling Means Defining Your Customer's Problems!
    ("4_JQQoMBp1I", "Jim Keenan", "Provement"),  # Gap Selling By Jim Keenan: The Best Salesbook Ever?
    ("OCcmy6gUEns", "Jim Keenan", "Sales for Life"),  # Social Learning: How the Best Sales People Learn
    ("hbn75sng0Es", "Jim Keenan", "Kerry Sullivan"),  # How To Kick Ass In Sales Interview
    ("SxD4vHKZsXw", "Jim Keenan", "Sales Feed"),  # 3 Steps to Achieve Success in Closing
    ("aqxm68tR59M", "Jim Keenan", "Keenan"),  # Objections: The Sign of Horrible Selling
    ("sey54Hu7O4c", "Jim Keenan", "Keenan"),  # The ONE Discovery Question - GAME CHANGER!
    ("Qns0rsE4Ojw", "Jim Keenan", "Keenan"),  # Building the Gap Between Sales
    ("HePENL6liYA", "Jim Keenan", "CNBC Television"),  # BlackRock's Jim Keenan breaks down strategy
    # Justin Michael (JMM / HYPCCCYCL)
    ("E6XT502Ot98", "Justin Michael", "FunnelFLARE"),  # Using the Route, Ruin, Multiply Technique for Cold Calling
    ("42wvhFemn2E", "Justin Michael", "HYPCCCYCL"),  # Anthony Iannarino - Role call cold call
    ("rY2ob3fcphE", "Justin Michael", "Outbound Business Development"),  # Apollo.io: A Modern Tech Stack for Outbound Sales
    ("qpUnYwqSw5Q", "Justin Michael", "Oren Klaff"),  # Would the CEO of a $500MM company open your COLD Email?
    ("PbdvDL7ZBwU", "Justin Michael", "Trent Dressel"),  # How To Cold Email Clients (Best Cold Email Templates)
    ("GkrZau1w4g4", "Justin Michael", "Gerhard Gschwandtner"),  # HOW TO REACH MORE PROSPECTS WITH RIGHTBOUND
    ("4Od3fn2Of7U", "Justin Michael", "RightBound"),  # Tenbound, The Sales Development Podcast
    # John Barrows (new videos)
    ("HLouBf1OcVg", "John Barrows", "John Barrows"),  # Why Buyer Enablement Beats Sales Enablement
    ("d5UnXlfS3ok", "John Barrows", "John Barrows"),  # How to Sell Like a CEO ($100M+ in Sales)
    ("Zszw1GwT170", "John Barrows", "John Barrows"),  # Owning the Pipeline Like a CEO with Leslie Venetz
    ("dPk9Wra5Fgw", "John Barrows", "John Barrows"),  # The Truth About SDR to AE Promotions
    ("-aPvDOs0nuA", "John Barrows", "John Barrows"),  # Email the CEO directly
    ("1Fa1__jqBGY", "John Barrows", "John Barrows"),  # Summary Email to Hold the prospect accountable
    ("Ax95JI2JkBI", "John Barrows", "John Barrows"),  # LinkedIn tactics to set meetings (don't pitch slap!)
    ("eu3mTn9Qt2k", "John Barrows", "John Barrows"),  # 3 Questions Every B2B AE Must Ask
    ("r4gCTo2PtkY", "John Barrows", "John Barrows"),  # Increase deal size, find urgency, de-risk the decision
    ("SvKDqwtajOQ", "John Barrows", "John Barrows"),  # Should You Ever Negotiate Over Email?
    ("fvQ94TeDrLU", "John Barrows", "John Barrows"),  # The NeuroStrategy Behind Buyer Behavior
    ("IbKn80AA6r8", "John Barrows", "John Barrows"),  # The Sales Side of Hiring
    ("-9d5frqRwcQ", "John Barrows", "John Barrows"),  # The Cold Call Structure That Actually Works In 2026
    ("0r4o16UxL9M", "John Barrows", "John Barrows"),  # $2.3B in Sales Truths
    # Josh Braun (new videos)
    ("bEOwAPnyT1A", "Josh Braun", "Josh Braun"),  # Sales Pressure: Turning Down the Temperature
    ("-yWiaoxvKQE", "Josh Braun", "Josh Braun"),  # Sales Training With memoryBlue
    ("PWZlC5ZuGLg", "Josh Braun", "Josh Braun"),  # Selling Cookies
    ("rYPksXxSgL8", "Josh Braun", "Josh Braun"),  # Ditch the Pitch
    ("emBwLDiH5zU", "Josh Braun", "Josh Braun"),  # Selling Honey to My Honey
    ("OUEAdHEbzZU", "Josh Braun", "Josh Braun"),  # Selling Socks to People Who Have Socks
    ("L0gZMLjLXyc", "Josh Braun", "Josh Braun"),  # A Common Sales Mistake
    ("JR-SFQ-DqV8", "Josh Braun", "Josh Braun"),  # What a NY Deli Can Teach You About Sales
    ("iRnKXu0cFvE", "Josh Braun", "Josh Braun"),  # Cold Call Pop Quiz
    ("M_YqXiBAJKE", "Josh Braun", "Josh Braun"),  # A Common Sales Mistake
    ("cq1kr-DuW3c", "Josh Braun", "Josh Braun"),  # The Hard Sell is Getting Harder to Sell
    ("EwgNC3LHkbQ", "Josh Braun", "Josh Braun"),  # How to Deal With Angry People
    ("XCCu-UvcjeQ", "Josh Braun", "Josh Braun"),  # How to Sell Without Sounding Salesy
    ("B5GsJ459jYY", "Josh Braun", "Josh Braun"),  # Selling is a Transfer of Confidence
    ("cKMMLzKQsdc", "Josh Braun", "Josh Braun"),  # 9 Things I Learned About Sales
    # Julie Hansen
    ("5Ellizrf2Vk", "Julie Hansen", "Crystal Knows"),  # Sales Engagement on Video with Julie Hansen
    ("YaStBdLeoSo", "Julie Hansen", "Heinz Marketing"),  # Sales Pipeline Radio - Julie Hansen
    # Kwame Christian
    ("evSqkcPtGRw", "Kwame Christian", "Kwame Christian Esq., M.A."),  # Who Should Make the First Offer?
    ("8xCff2r7L4k", "Kwame Christian", "Kwame Christian Esq., M.A."),  # From People Pleaser to Negotiation Pro
    ("5twTXNbM1Tc", "Kwame Christian", "Kwame Christian Esq., M.A."),  # From People Pleaser to Master Negotiator
    ("-qGXxiMjMc8", "Kwame Christian", "Kwame Christian Esq., M.A."),  # Right vs. Persuasive: Negotiation Secrets
    ("CgLGdnCbdds", "Kwame Christian", "Kwame Christian Esq., M.A."),  # Negotiate Like a Pro
    ("0QpFc6vtc8c", "Kwame Christian", "Kwame Christian Esq., M.A."),  # Testimonials for American Negotiation Institute
    ("jHutBJvsCyg", "Kwame Christian", "Kwame Christian Esq., M.A."),  # Testimonials for American Negotiation Institute
    ("sSYkhv3Cm5U", "Kwame Christian", "Negotiate Anything (Audio Podcast)"),  # DEI's Value in Sales, Negotiation, and Leadership
    ("ikS8slduv78", "Kwame Christian", "Kwame Christian Esq., M.A."),  # The 3-Step Framework to Win Any Negotiation
    ("vrDzCpa_FqQ", "Kwame Christian", "Kwame Christian Esq., M.A."),  # Negotiation Is Just Asking for What You Want
    ("Vy6mkXQzndo", "Kwame Christian", "Kwame Christian Esq., M.A."),  # The Perfect Way to Anchor a Deal
    ("DQzABaUfxX4", "Kwame Christian", "Kwame Christian Esq., M.A."),  # Redefining Negotiation: It's Every Conversation
    ("w_AcIkg3eNM", "Kwame Christian", "Kwame Christian Esq., M.A."),  # How to Price a Business in Negotiation
    ("kyVlmH90nAw", "Kwame Christian", "Kwame Christian Esq., M.A."),  # The Anchoring Trick That Changes Every Negotiation
    ("4-fooQl6o4s", "Kwame Christian", "Kwame Christian Esq., M.A."),  # Compassionate Curiosity in a Heated Negotiation
    # Kyle Coleman
    ("rUxnsGKsDfk", "Kyle Coleman", "Insightly CRM by Unbounce"),  # Standing out in Sales: Building Your Personal Brand
    ("0v1OQ-kHbwE", "Kyle Coleman", "Sales Feed"),  # How to Create Personalized Sales Messaging
    ("7rTaZTl3GE4", "Kyle Coleman", "30 Minutes to President's Club"),  # 15 Expert B2B Sales Tips in 7-Minutes
    ("UJ0_n5fyXWg", "Kyle Coleman", "CopyAI"),  # Pipeline Acceleration: How AI Helps Sales Productivity
    ("R55Vo3kRqak", "Kyle Coleman", "Insightly CRM by Unbounce"),  # The Sales-to-Marketing Career Change
    ("TdrSrTT9Ucw", "Kyle Coleman", "Team Sales Assembly"),  # Sales Assembly Study Break Featuring Kyle Coleman
    ("J5wHcbea9Sg", "Kyle Coleman", "Clari"),  # Kyle Coleman on using ChatGPT for prospecting
    ("LnuVJpTfAyw", "Kyle Coleman", "Mark Allen"),  # How Clari + your CRM can Supercharge
    ("iiWRSOu3G9g", "Kyle Coleman", "Wynter"),  # 3 Go-to-Market bets we are making this year
    ("mofpSi8_f-8", "Kyle Coleman", "SaaStock"),  # How To Run Revenue For Sustainable Growth
    ("abb4Sp0N1_g", "Kyle Coleman", "Sales Feed"),  # Why Salespeople NEED to Be Prospecting
    ("F3J7iToDZKQ", "Kyle Coleman", "Sales Unfiltered"),  # How to keep a prospect engaged?
    # Maria Bross
    ("sqmpbYdI4XY", "Maria Bross", "Atonom"),  # 3 Win Rate Obstacles Solved with AI
    ("NNjonkz57lY", "Maria Bross", "Tom Alaimo"),  # Millennial Sales Podcast 192
    ("iSQjuzCKuwo", "Maria Bross", "Sales Stories IRL"),  # SSIRL Episode 57: Maria Bross
    ("SxoHAglVurw", "Maria Bross", "Sell Better"),  # How to Overcome the Fear of Cold Calling
    ("AMIZUy8p-7A", "Maria Bross", "Tom Alaimo"),  # 3 Tips To Develop Confidence
    # Mark Hunter
    ("d9z5xmsxQz4", "Mark Hunter", "Mark Hunter"),  # Strategies to Grow Revenue and Increase Customers
    ("XbzETYDIQrQ", "Mark Hunter", "Mark Hunter"),  # Transform Customer Onboarding into a Sales Engine
    ("ked62MGpMro", "Mark Hunter", "Mark Hunter"),  # Discovery Calls, LinkedIn, and the Future of Sales
    ("kBqzdWalJcc", "Mark Hunter", "Mark Hunter"),  # The Sale is Made in the Follow-Up
    ("BSMFhS7KuxM", "Mark Hunter", "Mark Hunter"),  # How to Have a Prospecting Mindset
    ("47SxDM96WyU", "Mark Hunter", "Mark Hunter"),  # How to Have a Prospecting Mindset
    ("I8zYY5iYEEc", "Mark Hunter", "Mark Hunter"),  # Sales Logic: Mastering The Art of the Cross Sell
    ("iZQWRHZ2roU", "Mark Hunter", "Mark Hunter"),  # Why Selling with Integrity Is the Future of Sales
    ("IJOrD93a540", "Mark Hunter", "Mark Hunter"),  # AI, LinkedIn, and the Future of Sales Outreach
    ("YecPE0Ooidc", "Mark Hunter", "Mark Hunter"),  # The New Rules of LinkedIn for Sales in the Age of AI
    ("Yw_UhfsLoe0", "Mark Hunter", "Mark Hunter"),  # Measure Sales Success Beyond the Quota
    ("Q2ZmMGeHC-U", "Mark Hunter", "Mark Hunter"),  # Sales Logic: How to Win Over the CFO
    ("nKdbRslJDKA", "Mark Hunter", "Mark Hunter"),  # Selling Across Cultures
    ("D-4em6j4HOw", "Mark Hunter", "Mark Hunter"),  # Outbound Prospecting Isn't Dead - It's Just Different
    ("NTqIy090q6w", "Mark Hunter", "Mark Hunter"),  # Sales Leadership That Inspires Confidence and Results
    # Mark Kosoglow
    ("iQ7iTcajcUU", "Mark Kosoglow", "Inside Sales Excellence"),  # Sales Judo: Master the Art and Science of Closing
    ("XWR6nnrZgZk", "Mark Kosoglow", "Sell Better"),  # Multithreading Tips for Enterprise Accounts
    ("Jv4b1lYmd5k", "Mark Kosoglow", "Emblaze | Revenue Community by Corporate Visions"),  # Account Based Selling
    # Mo Bunnell
    ("BqXAarQoGZk", "Mo Bunnell", "Mo Bunnell"),  # Introducing GrowBIG AI: Your Business Development Coach
    ("-a1XP51SDMU", "Mo Bunnell", "Mo Bunnell"),  # Get More Revenue. Win More Work.
    ("uzMTnYy6nvs", "Mo Bunnell", "Michael Gionta"),  # Fill Your Pipeline by Asking the Right Questions
    ("ZjU4yoxyZd8", "Mo Bunnell", "Manny Talks TV"),  # Sell Like Crazy Unboxing, Review and Summary
    ("zCZsOYoAf8s", "Mo Bunnell", "Mickey Mellen"),  # Book summary of Give to Grow by Mo Bunnell
    ("JOX7dAtc0uc", "Mo Bunnell", "Google Play Books"),  # The Snowball System: How to Win More Business
    ("1gKZduRZS2E", "Mo Bunnell", "John Wooten"),  # Mo Bunnell: Mastering Growth with The Snowball System
    ("A_pf_qJ7HMo", "Mo Bunnell", "Arke"),  # MO BUNNELL - Understanding Buying Behaviors
    # Morgan J Ingram (new videos)
    ("gY2RPCbEnvU", "Morgan J Ingram", "Morgan J Ingram"),  # How To Create LinkedIn Content That Drives B2B Sales
    ("vxsyN2vCUVk", "Morgan J Ingram", "Morgan J Ingram"),  # How to Build a Revenue Team That Sells AND Brands
    ("Z1CkDVQY16w", "Morgan J Ingram", "Morgan J Ingram"),  # How to Build Pipeline Using LinkedIn Sales Navigator
    ("l-UKwVS8ENc", "Morgan J Ingram", "Morgan J Ingram"),  # What's Actually Working in Outbound Right Now
    ("Ukn80m3Uyrc", "Morgan J Ingram", "Morgan J Ingram"),  # 3 Ways to Use Buyer Signals to Start Sales Conversations
    ("8HYeeMvodbE", "Morgan J Ingram", "Morgan J Ingram"),  # How to Win on LinkedIn with Personality
    ("53lGAJBwkyE", "Morgan J Ingram", "Morgan J Ingram"),  # 3 LinkedIn DM Tactics for Outbound
    ("HAhtO6fdbfY", "Morgan J Ingram", "Morgan J Ingram"),  # 5 Steps to Create Outbound Videos That Convert
    ("IOszR23F5Pk", "Morgan J Ingram", "Morgan J Ingram"),  # 5 LinkedIn AI Strategies That Book Sales Calls
    ("qktFZmgMJ3U", "Morgan J Ingram", "Morgan J Ingram"),  # LinkedIn Messaging Hack Made Me $120,000
    ("xiK6u1NWgoo", "Morgan J Ingram", "Morgan J Ingram"),  # LinkedIn CEO Content Strategy: Zero to Hero in 60 Days
    ("JOeeMAt6J_w", "Morgan J Ingram", "Morgan J Ingram"),  # Why LinkedIn is the Best Platform for B2B Growth
    ("nUe5IpnleRc", "Morgan J Ingram", "Morgan J Ingram"),  # LinkedIn Outbound Strategy: 25+ Meetings a Month
    ("pVeDwWmUELw", "Morgan J Ingram", "Morgan J Ingram"),  # How to Close 10 Clients in 30 Days on LinkedIn
    ("3uFGRAfosA8", "Morgan J Ingram", "Morgan J Ingram"),  # 5 Ways to Increase Your Sales Pipeline in 30 Days
    # Nate Nasralla (new videos)
    ("eqrczCp3WCE", "Nate Nasralla", "Sales Feed"),  # Champion Enablement: The Missing Piece in B2B Sales
    ("U6h9sF3NaTg", "Nate Nasralla", "NaNLABS"),  # Fluint's B2B Sales Enablement Solution
    ("7rTaZTl3GE4", "Nate Nasralla", "30 Minutes to President's Club"),  # 15 Expert B2B Sales Tips in 7-Minutes
    ("rhG2M4zmwAY", "Nate Nasralla", "Sandler By Jabulani"),  # Book Review Nate Nasralla Selling With
    ("V3KlbC0Mx2Y", "Nate Nasralla", "Salesloft"),  # Operational rhythm is the key to sales execution
    ("ogJCAF0UDCk", "Nate Nasralla", "Joe Milnes"),  # Paper Will TRIPLE Your Close Rate in 2026
    ("N96guscBWR4", "Nate Nasralla", "Sales Players"),  # Making the Most of Your Tech Sales Career
    ("OBObvYd7HXc", "Nate Nasralla", "Sales Players"),  # 20 Sales Plays I Run When Nothing Else Is Working
    ("TYbDZlHCDqw", "Nate Nasralla", "Sales Players"),  # 20 Sales Plays I Run When Nothing Else Is Working
    ("JOr5JmXnaaI", "Nate Nasralla", "Chris Orlob at pclub"),  # Bullet Proof Business Case Writing
    ("nL9kQEZBiTI", "Nate Nasralla", "Mixmax"),  # Interview with Fluint Co-Founder Nate Nasralla
    ("x3-bX9DtSRE", "Nate Nasralla", "Sales Stories IRL"),  # SSIRL Episode 5: Nate Nasralla
    # Nick Cegelski (new videos)
    ("oW6fnZC_tFQ", "Nick Cegelski", "30 Minutes to President's Club"),  # 21 Dangerous Discovery Questions
    ("cykZ1WU5Se4", "Nick Cegelski", "Mor Assouline"),  # 3 Tactics for starting a sales call & demo
    ("84ozb-o4qVE", "Nick Cegelski", "Sales Feed"),  # Make the Most of Your Sales Discovery Calls
    ("hVtfsq0McNQ", "Nick Cegelski", "Insightly CRM by Unbounce"),  # Manage Pipeline Like a President's Club Seller
    ("4e2kEQ_VbV8", "Nick Cegelski", "The Sales Topics Podcast"),  # Coaching Culture - Episode 12
    ("WMTEW8R0voo", "Nick Cegelski", "Emblaze | Revenue Community by Corporate Visions"),  # Nick Cegelski on Activity
    ("q0B8FB3GMDk", "Nick Cegelski", "Woodpecker.co"),  # Nick Cegelski's best cold email advice
    ("BppUJZ6HmxY", "Nick Cegelski", "30 Minutes to President's Club"),  # Handling Nasty Cold Call Objections
    # Niraj Kapur
    ("3_ZLJT1BfyE", "Niraj Kapur", "Everybody Works In Sales"),  # Non sales and non LinkedIn book recommendations
    ("K-BbUwEtTXU", "Niraj Kapur", "Victor Antonio"),  # Sell The Unstated Needs - Sales Influence Podcast
    ("-NvuW_K7d6Y", "Niraj Kapur", "Janice B Gordon"),  # Scale Your Sales Podcast with Niraj Kapur
    ("2fl4Y7_cA-Q", "Niraj Kapur", "Revel Movement - StartUp School"),  # How to sell when times are tough
    ("6YQAqXm_cHc", "Niraj Kapur", "The Effective Marketing Company"),  # The power of vulnerability in sales
    ("-FSyeSWZ9mM", "Niraj Kapur", "Jordan Stupar"),  # How to Build Urgency, Shorten Sales Cycles
    ("iFsxtnTp7ZI", "Niraj Kapur", "Gerhard Gschwandtner"),  # Hacking Sales in Real Time
    ("u4I2pWdW2xM", "Niraj Kapur", "Lane Ethridge"),  # "I don't have money" objection
    ("MXR586ODQEY", "Niraj Kapur", "Kenny Casimir"),  # How To Handle "I Don't Have The Money" Objection
    # Rosalyn Santa Elena
    ("RPvyx26u4Ww", "Rosalyn Santa Elena", "More SaaStr"),  # Revolutionizing Enterprise Sales Growth
    ("Wv2hUJQCfHo", "Rosalyn Santa Elena", "Traction Complete"),  # Pipeline reporting and forecasting
    ("-sm3Pw9BcaU", "Rosalyn Santa Elena", "Revenue Operations and Enablement"),  # The Why and What of Sales Operations
    ("rSSiHL_XTKQ", "Rosalyn Santa Elena", "Orchestrate Sales"),  # REVOPS vs Sales Enablement
    ("F85JRP2kmVY", "Rosalyn Santa Elena", "Revenue Operations and Enablement"),  # Using AI in Revenue Operations
    ("ZGQsthni89s", "Rosalyn Santa Elena", "Ebsta"),  # Democratizing Sales Excellence
    ("W5XqM58INgM", "Rosalyn Santa Elena", "DemandMatrix"),  # Pipeline Analytics
    ("os4qnXd3dVM", "Rosalyn Santa Elena", "Traction Complete"),  # Fundamentals of compensation planning
    ("n-nWuOH0I-k", "Rosalyn Santa Elena", "Salesloft"),  # Inside RevOps: Rethinking for the Modern Buyer
    ("LImwstg5lrg", "Rosalyn Santa Elena", "Salesloft"),  # Inside RevOps: Fixing your Revenue Frankenstack
    ("MWefaz8uN5U", "Rosalyn Santa Elena", "Revenue Enablement Institute"),  # Revenue Operations in a 21st Century Model
    ("Y4EUbUgMIuc", "Rosalyn Santa Elena", "Nasdaq"),  # Digital Transformation: It's Called RevOps
    ("IfrjdMgGze0", "Rosalyn Santa Elena", "Market Recruitment"),  # Challenges of Working in Revenue Operations
    ("Gz4ofLoz45E", "Rosalyn Santa Elena", "CS2 - GTM Ops"),  # Revenue Operations Documentation
    ("fQoEcH19USY", "Rosalyn Santa Elena", "TalkDataToMe Clips"),  # Data Horror Story | Rosalyn Santa Elena (Clari)
    # Samantha McKenna (new videos)
    ("nDdNPHNHPCg", "Samantha McKenna", "Samantha McKenna - #samsales"),  # How to Actually Sell with LinkedIn Sales Navigator!
    ("jwEAi3A7PGM", "Samantha McKenna", "Samantha McKenna - #samsales"),  # LinkedIn Sales Navigator Play for Exec Access
    ("s2lU71vX6j8", "Samantha McKenna", "Samantha McKenna - #samsales"),  # LinkedIn Sales Navigator - Day 1 - Intro
    # Sarah Brazier
    ("6P4ixkCJWlQ", "Sarah Brazier", "Daily Sales Tips"),  # THIS is how to prospect on LinkedIn
    ("D_249H9nY2k", "Sarah Brazier", "Flow State Sales"),  # Turning Objections into Discovery Opportunity
    ("C4ezQreS9fU", "Sarah Brazier", "Solomon Thimothy"),  # How to Improve Your Sales with Gong
    ("oL4WMMVSLko", "Sarah Brazier", "SDR Nation"),  # LinkedIn Personal Branding 101
    ("0v1OQ-kHbwE", "Sarah Brazier", "Sales Feed"),  # How to Create Personalized Sales Messaging
    ("ndI_xYvoK1U", "Sarah Brazier", "Sell Better"),  # 18-Minutes of World Class Outbound Sales Tips
    ("76vXx-sd4I0", "Sarah Brazier", "Daily Sales Tips"),  # Empathize and Just Have a Conversation
    ("aiiJKvh_wog", "Sarah Brazier", "Daily Sales Tips"),  # Using Cameo to Book a Sales Meeting
    ("KFjvmrCwdKk", "Sarah Brazier", "Dimmo"),  # How UserGems Makes Sales and Marketing Easier
    ("WRdcANZIEWo", "Sarah Brazier", "Sales Feed"),  # When Should Sales Reps STOP Calling?
    ("xqLH2-kUHaU", "Sarah Brazier", "Brett Gray"),  # 7 Questions with Sarah Brazier
    ("HUO99MJDXxE", "Sarah Brazier", "Scratchpad"),  # Minisode #1 with Sarah Brazier
    ("LksUPQxI8Go", "Sarah Brazier", "Scratchpad"),  # Episode 23: Sarah Brazier
    ("SxoHAglVurw", "Sarah Brazier", "Sell Better"),  # How to Overcome the Fear of Cold Calling
    # Scott Leese
    ("h6IjHkeiWnw", "Scott Leese", "The Scott Leese"),  # Follow-Up Next Time a Prospect Ghosts You
    ("9av0lKbFdnA", "Scott Leese", "The Scott Leese"),  # You Can't Close Every Deal Yourself
    ("WQCgvil5ZsM", "Scott Leese", "The Scott Leese"),  # 4 Words That Close Any Deal
    ("GQA4XwSmeQg", "Scott Leese", "The Scott Leese"),  # 20 Years of No-BS SaaS Sales Advice in 7 Minutes
    ("NGo1Rg89VKw", "Scott Leese", "The Scott Leese"),  # The Smartest Follow-Up Move to Close Deals
    ("dZVBEi1qgVM", "Scott Leese", "The Scott Leese"),  # Build a Sales Pipeline in 24 Hours
    ("LSYM5b-ihpg", "Scott Leese", "The Scott Leese"),  # Full-Time VPs of Sales Get Expensive FAST
    ("6Tcb5cmgdro", "Scott Leese", "The Scott Leese"),  # You're Not Selling Because You Talk Too Much
    ("Yh7b4XiSddo", "Scott Leese", "The Scott Leese"),  # What Sales Leaders Are Actually Expected To Do
    ("YRYSybg1UQY", "Scott Leese", "The Scott Leese"),  # Sales Leaders, We Need To Talk
    ("HegjSiX4cKI", "Scott Leese", "The Scott Leese"),  # Outbound Isn't For Meetings Anymore
    ("5a0zJz8MOj8", "Scott Leese", "The Scott Leese"),  # The Fastest Way to Rise in Sales
    ("QC3lLh0MJic", "Scott Leese", "The Scott Leese"),  # The Smartest Cold Call Move EVER
    ("5Oihob8zGU0", "Scott Leese", "The Scott Leese"),  # What You REALLY Need to Train For Sales
    # Shari Levitin
    ("LM4n_nfVcmg", "Shari Levitin", "Shari Levitin"),  # How to Rehumanize the Sales Process
    ("JlEnV5Ni-w0", "Shari Levitin", "Shari Levitin"),  # Sales Tip Of The Day: Closing
    ("mYOnNZoiXNI", "Shari Levitin", "Shari Levitin"),  # This Is How I Close Sales
    ("rxrL7DeydF0", "Shari Levitin", "Shari Levitin"),  # How to Coach Sales Reps to Close Deals This Quarter
    ("vxVEOeG09WI", "Shari Levitin", "Shari Levitin"),  # ROI Won't Close The Deal - But This Will!
    ("HlmmP_8b48I", "Shari Levitin", "Shari Levitin"),  # When You Get A Sales Objection
    ("ukroEwhcP20", "Shari Levitin", "Shari Levitin"),  # The Power of StorySelling
    ("2uqd5lbuY40", "Shari Levitin", "Shari Levitin"),  # The Importance Of Discovery In Sales
    ("7F7vFJCCgn8", "Shari Levitin", "Shari Levitin"),  # 3 Questions That Drive Sales Success
    ("zA9suy4jOAw", "Shari Levitin", "Shari Levitin"),  # Get the RIGHT Sales Training
    ("Eb93TWHI2XU", "Shari Levitin", "Shari Levitin"),  # Story Selling
    ("lRD2QjgzcoI", "Shari Levitin", "Shari Levitin"),  # Torturing Sales People
    ("9myX0MQevyw", "Shari Levitin", "Shari Levitin"),  # Rules For LinkedIn Account
    ("LoYN2vVsl8k", "Shari Levitin", "Shari Levitin"),  # What Are The 5 Why's Of Selling
    ("8ZqTUTyt9AE", "Shari Levitin", "Shari Levitin"),  # Sales Tips: Answering Questions
    # Tiffani Bova
    ("IM_YAL4eKdI", "Tiffani Bova", "Tiffani Bova"),  # Smart Selling: Tips to Grow Your Sales Career
    ("mIGz6XOfL_k", "Tiffani Bova", "Tiffani Bova"),  # LinkedIn Sales Solutions Showcase Studio Week
    ("8Yt56k1KJwI", "Tiffani Bova", "Tiffani Bova"),  # Salesforce Customer Expectations
    ("RJRfY2-aX9s", "Tiffani Bova", "Tiffani Bova"),  # Leadership Goes Beyond
    ("LRk1U7gnAFM", "Tiffani Bova", "Tiffani Bova"),  # THINK FORWARD: Deep Sales
    ("Hrg5Mf4qNNA", "Tiffani Bova", "Tiffani Bova"),  # Customer lifetime value
    ("_5XyV-rRk6g", "Tiffani Bova", "Tiffani Bova"),  # Next step for sales technology
    ("wQWg5LMFzn4", "Tiffani Bova", "Tiffani Bova"),  # Future of Selling: Contextual Data Driven
    ("MRbLFi71s_o", "Tiffani Bova", "Tiffani Bova"),  # TCU Sales Academy
    ("ADYqKHJyXO8", "Tiffani Bova", "Tiffani Bova"),  # Leading Europe's Largest Software IPO
    ("LSHyuJjHScA", "Tiffani Bova", "Tiffani Bova"),  # Customer Service Industry Changes
    ("SC1jFAWqJIA", "Tiffani Bova", "Tiffani Bova"),  # Macquarie Group: Pivoting to customer experience
    ("Nl4jYxficlQ", "Tiffani Bova", "Tiffani Bova"),  # Pinpointing Customer Disruption
    ("k-9VSMQQFrU", "Tiffani Bova", "Tiffani Bova"),  # Don't Let Anyone Crush Your Dreams
    # Will Aitken (new videos)
    ("y0H0CdpJ5wk", "Will Aitken", "Will Aitken"),  # Sell Better, Hot Tubs, & Sales Influencers
    ("CEfaeEktOcQ", "Will Aitken", "Will Aitken"),  # Will Aitken Sales Live Stream
    ("pTrIHy4p6gU", "Will Aitken", "Will Aitken"),  # Hubspot Inbound 2025
    ("mmQbqX3Whak", "Will Aitken", "Will Aitken"),  # I Challenged LinkedIn Influencers
    ("T-Oop0eejlU", "Will Aitken", "Salesloft"),  # No Nonsense Sales: Will Aitken sales roleplay
    ("ndI_xYvoK1U", "Will Aitken", "Sell Better"),  # 18-Minutes of World Class Outbound Sales Tips
    ("V0NZ_4GoLJM", "Will Aitken", "Sell Better"),  # The Perfect Discovery Call for Software Sales
    ("Tss-AZgd9Cg", "Will Aitken", "Lavender"),  # Which Sales Influencer Can Write Best Cold Email?
    ("NxtUiL0s2O0", "Will Aitken", "Sell Better"),  # Close More Deals With These Three Sales Tips
    ("V5I8UReVnL4", "Will Aitken", "Will Aitken"),  # Live Cold Calling with Salesfinity
    ("gdBdXP_Xkcs", "Will Aitken", "Will Aitken"),  # Live Cold Calling with Salesfinity
]

OUTPUT_FILE = TMP_DIR / "youtube_raw.json"
ERROR_LOG = TMP_DIR / "youtube_errors.log"

# Chunking settings
CHUNK_SIZE = 500  # words
CHUNK_OVERLAP = 50  # words


def get_existing_video_urls() -> set[str]:
    """Fetch existing video URLs from Airtable to skip re-processing."""
    if not AIRTABLE_API_KEY or not AIRTABLE_BASE_ID or not AIRTABLE_TABLE_NAME:
        logger.info("Airtable not configured, processing all videos")
        return set()

    try:
        base_id = AIRTABLE_BASE_ID.split("/")[0]
        api = Api(AIRTABLE_API_KEY)
        table = api.table(base_id, AIRTABLE_TABLE_NAME)
        records = table.all()

        urls = {record["fields"].get("Source URL", "") for record in records}
        logger.info(f"Found {len(urls)} existing videos in Airtable (will skip)")
        return urls

    except Exception as e:
        logger.warning(f"Could not fetch Airtable records: {e}")
        logger.info("Processing all videos")
        return set()


def chunk_transcript(
    text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP
) -> list[dict[str, any]]:
    """Split transcript into overlapping chunks."""
    words = text.split()
    chunks = []

    if len(words) <= chunk_size:
        return [{"chunk_index": 0, "content": text, "start_word": 0}]

    start = 0
    chunk_index = 0

    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunk_words = words[start:end]

        chunks.append(
            {
                "chunk_index": chunk_index,
                "content": " ".join(chunk_words),
                "start_word": start,
            }
        )

        chunk_index += 1
        start = end - overlap

        if start >= len(words) - overlap:
            break

    return chunks


_proxy_url = os.environ.get("DECODO_PROXY_URL")
if _proxy_url:
    logger.info("Decodo residential proxy enabled")


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(Exception),
    reraise=True,
)
def _fetch_transcript(video_id: str) -> list[any]:
    """Fetch transcript via proxy (new connection per request for IP rotation)."""
    if _proxy_url:
        api = YouTubeTranscriptApi(
            proxy_config=GenericProxyConfig(
                http_url=_proxy_url,
                https_url=_proxy_url,
            )
        )
    else:
        api = YouTubeTranscriptApi()
    return api.fetch(video_id)


def get_transcript(video_id: str) -> Optional[str]:
    """Fetch transcript for a YouTube video."""
    try:
        transcript_list = _fetch_transcript(video_id)
        full_text = " ".join([entry.text for entry in transcript_list])
        return full_text

    except TranscriptsDisabled:
        logger.warning(f"Transcripts disabled for {video_id}")
        return None

    except NoTranscriptFound:
        logger.warning(f"No transcript found for {video_id}")
        return None

    except Exception as e:
        logger.error(f"Error getting transcript for {video_id}: {e}")
        with open(ERROR_LOG, "a") as f:
            f.write(f"{datetime.now().isoformat()} - {video_id} - {e}\n")
        return None


def collect_transcripts() -> dict[str, any]:
    """Main collection function."""
    logger.info("Starting YouTube transcript collection...")

    # Get existing videos to skip
    existing_urls = get_existing_video_urls()

    # Filter to only new videos
    videos_to_process = [
        (vid, inf, ch)
        for vid, inf, ch in TARGET_VIDEOS
        if f"https://youtube.com/watch?v={vid}" not in existing_urls
    ]

    if not videos_to_process:
        logger.info("No new videos to process")
        return {
            "videos": [],
            "collection_date": datetime.now().isoformat(),
            "video_count": 0,
        }

    logger.info(
        f"Processing {len(videos_to_process)} new videos (skipping {len(TARGET_VIDEOS) - len(videos_to_process)} existing)"
    )

    all_videos = []

    for video_id, influencer, channel in videos_to_process:
        logger.info(f"Processing: {video_id} ({influencer})")

        transcript = get_transcript(video_id)

        if transcript:
            chunks = chunk_transcript(transcript)

            video_data = {
                "video_id": video_id,
                "influencer": influencer,
                "channel": channel,
                "url": f"https://youtube.com/watch?v={video_id}",
                "transcript_chunks": chunks,
                "date_collected": datetime.now().isoformat(),
                "source_type": "youtube",
            }

            all_videos.append(video_data)
            logger.info(f"  -> {len(chunks)} chunks extracted")

        time.sleep(RATE_LIMIT_YOUTUBE)

    # Save results
    output = {
        "videos": all_videos,
        "collection_date": datetime.now().isoformat(),
        "video_count": len(all_videos),
    }

    with open(OUTPUT_FILE, "w") as f:
        json.dump(output, f, indent=2)

    logger.info(f"Collected {len(all_videos)} videos -> {OUTPUT_FILE}")
    return output


if __name__ == "__main__":
    collect_transcripts()
