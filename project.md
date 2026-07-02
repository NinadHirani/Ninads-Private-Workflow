# AI Shorts Factory
## 01_Project_Overview.md
Version: 1.0
Author: AI Engineering Specification
Status: Draft

---

# 1. Project Overview

## Project Name

AI Shorts Factory

---

# Vision

Build a fully automated YouTube Shorts production system that can automatically:

- Find licensed short-form videos
- Download them
- Perform automatic editing
- Generate SEO metadata
- Upload to YouTube Shorts
- Run on a schedule
- Log all activity

The system must run locally using Docker and n8n and require minimal human interaction.

---

# Primary Goal

The primary goal is NOT to build an AI application.

The primary goal is:

Generate YouTube Shorts consistently to maximize:

- Views
- Watch Time
- Subscribers
- Revenue

using only licensed or reusable content.

---

# Business Objective

Create a system capable of publishing Shorts automatically while keeping operational costs extremely low.

Target monthly cost:

₹0 – ₹1000

---

# Scope

Included

✓ Licensed video collection

✓ Automated downloading

✓ Automated editing

✓ Metadata generation

✓ Automatic upload

✓ Scheduling

✓ Logging

✓ Analytics

Not Included

✗ Downloading copyrighted YouTube Shorts

✗ Copyright circumvention

✗ Manual editing

✗ Human video creation

---

# Success Criteria

The project is considered successful when it can:

1.
Run automatically every day.

2.
Find legal reusable videos.

3.
Download videos.

4.
Edit videos automatically.

5.
Generate metadata.

6.
Upload Shorts.

7.
Recover from failures automatically.

8.
Operate without user interaction.

---

# User

Single user

Runs locally on:

MacBook M1

---

# Target Platform

Primary

YouTube Shorts

Future

Instagram Reels

TikTok

Facebook Reels

---

# Development Philosophy

Everything must be

- Modular
- Replaceable
- Maintainable
- Open Source Friendly

Every module should be independently replaceable.

Example

Instead of

Pexels

future replacement

Pixabay

or

AI Generated Videos

should require changing only one module.

---

# Technology Stack

Automation

n8n

Containerization

Docker

Video Processing

FFmpeg

Programming

Python

Version Control

GitHub

APIs

YouTube Data API

Pexels API

Pixabay API

Optional Future

OpenAI

Claude

Google Veo

Kling

Runway

---

# System Requirements

MacOS

Apple Silicon

Docker Desktop

Git

Internet Connection

Google Account

YouTube Channel

Pexels API Key

---

# Folder Structure

AI-Shorts-Factory/

docker/

n8n/

downloads/

edited/

thumbnails/

captions/

music/

archive/

logs/

scripts/

ffmpeg/

prompts/

README.md

docker-compose.yml

---

# Functional Requirements

FR-001

Search licensed content.

---

FR-002

Download highest quality vertical videos.

---

FR-003

Automatically rename files.

---

FR-004

Store downloaded videos.

---

FR-005

Perform automatic editing.

---

FR-006

Generate titles.

---

FR-007

Generate descriptions.

---

FR-008

Generate hashtags.

---

FR-009

Upload videos.

---

FR-010

Schedule uploads.

---

FR-011

Maintain upload history.

---

FR-012

Retry failed uploads.

---

# Non Functional Requirements

The system should

- Be modular.

- Be fault tolerant.

- Be restartable.

- Require minimal maintenance.

- Recover after crashes.

- Continue running after reboot.

---

# Constraints

The system should avoid unnecessary paid services.

Local execution is preferred.

Docker must isolate services.

No platform-specific hacks.

---

# Expected Output

Every execution should produce

downloads/video.mp4

↓

edited/final.mp4

↓

Uploaded YouTube Short

↓

Log Entry

---

# Project Phases

Phase 1

Infrastructure

Docker

n8n

GitHub

APIs

---

Phase 2

Downloader

---

Phase 3

Video Editor

---

Phase 4

Metadata Generator

---

Phase 5

Uploader

---

Phase 6

Scheduling

---

Phase 7

Analytics

---

# Milestones

Milestone 1

Infrastructure Complete

Milestone 2

Downloader Complete

Milestone 3

Editing Complete

Milestone 4

Publishing Complete

Milestone 5

Automation Complete

---

# Risks

API Limits

YouTube API quota

Pexels API limits

FFmpeg failures

Network interruptions

Authentication expiration

Storage limitations

---

# Risk Mitigation

Retry Logic

Logging

Automatic restart

Health checks

Daily backups

---

# Acceptance Criteria

The project will be accepted when:

✓ One command starts the system.

✓ One workflow downloads a licensed video.

✓ The video is edited automatically.

✓ Metadata is generated.

✓ Video uploads successfully.

✓ Logs are generated.

✓ Scheduler works.

✓ Docker restart does not lose data.

---

# Version Roadmap

Version 1

Downloader

Editor

Uploader

---

Version 2

Better Editing

Captions

Music

---

Version 3

Analytics

Optimization

Trend Detection

---

Version 4

Multiple Channels

Multiple Niches

---

Version 5

Advanced AI Features

Performance Optimization

---

End of Document

# AI Shorts Factory
## 02_System_Architecture.md
Version: 1.0

---

# Purpose

This document defines the complete architecture of the AI Shorts Factory system.

It explains every service, every folder, every communication path, and every responsibility of each module.

The objective is to ensure that every component is independent, replaceable, and scalable.

---

# System Architecture

```
                           USER

                             │

                             ▼

                    Docker Compose

                             │

        ┌────────────────────┼────────────────────┐

        ▼                    ▼                    ▼

      n8n                FFmpeg              Python

        │                    │                    │

        └──────────────┬─────┘

                       ▼

               Local File Storage

                       ▼

                  YouTube API

```

---

# Main Components

## 1. Docker

Responsibilities

- Run every service
- Isolate dependencies
- Persistent storage
- Easy deployment
- Restart services automatically

---

## 2. n8n

Responsibilities

- Workflow orchestration
- Scheduling
- API communication
- Retry logic
- Error handling
- Logging
- Triggering FFmpeg
- Triggering Python scripts

n8n DOES NOT edit videos.

It only coordinates.

---

## 3. FFmpeg

Responsibilities

- Crop
- Resize
- Convert
- Merge clips
- Add music
- Add fade
- Normalize audio
- Encode MP4

No AI.

Only media processing.

---

## 4. Python

Responsibilities

Small helper scripts only.

Examples

- Ranking videos
- Metadata cleanup
- Filename generation
- Analytics processing

Python should never duplicate FFmpeg functionality.

---

## 5. Local Storage

Purpose

Temporary working directory.

Folders

downloads/

edited/

archive/

logs/

---

## 6. APIs

### YouTube

Purpose

Upload Shorts

Create metadata

Scheduling

Status updates

---

### Pexels

Purpose

Search videos

Download videos

Retrieve metadata

---

### Pixabay

Future backup source.

---

# Architecture Principles

Every module has exactly one responsibility.

Example

GOOD

Downloader

↓

Editor

↓

Uploader

BAD

Downloader

Editor

Uploader

Metadata

Analytics

Inside one workflow.

---

# Communication

n8n

↓

HTTP API

↓

Pexels

↓

JSON

↓

n8n

↓

Binary Video

↓

FFmpeg

↓

Edited Video

↓

YouTube API

↓

Upload

↓

Analytics

---

# Storage Flow

downloads/

↓

edited/

↓

archive/

The original download is never overwritten.

---

# Error Handling

Every module returns

SUCCESS

or

FAILED

Never return ambiguous states.

---

# Retry Strategy

API Failure

Retry 3 times.

Network Failure

Retry 3 times.

Authentication Failure

Stop workflow.

Notify user.

FFmpeg Failure

Move video to logs.

Continue with next job.

---

# Logging

Every module writes logs.

Example

Timestamp

Workflow

Execution Time

Video ID

Upload Status

Error Message

Retry Count

---

# Folder Architecture

```
AI-Shorts-Factory/

docker/

n8n/

downloads/

edited/

archive/

logs/

scripts/

ffmpeg/

prompts/

music/

captions/

thumbnails/
```

---

# Docker Architecture

```
Docker

↓

n8n

↓

Volume

↓

AI_Shorts_Factory

↓

Downloads

↓

Edited

↓

Archive
```

---

# Environment Variables

Store in

.env

Never hardcode.

Variables

PEXELS_API_KEY

PIXABAY_API_KEY

YOUTUBE_CLIENT_ID

YOUTUBE_CLIENT_SECRET

YOUTUBE_REFRESH_TOKEN

LOG_LEVEL

DOWNLOAD_PATH

EDIT_PATH

ARCHIVE_PATH

---

# Security

Never expose

API Keys

OAuth Secrets

Client Secrets

Refresh Tokens

Passwords

Never commit them to GitHub.

---

# Data Flow

Scheduler

↓

Topic

↓

Content Finder

↓

Downloader

↓

Editor

↓

Metadata

↓

Uploader

↓

Logger

↓

Archive

---

# Scalability

Current

1 Channel

Future

10 Channels

Current

1 Video

Future

100 Videos

Current

Pexels

Future

Multiple APIs

Architecture must not change.

Only modules change.

---

# Monitoring

Monitor

Workflow duration

Download success

Upload success

Disk usage

API failures

Quota usage

---

# Backup Strategy

Daily

Export n8n workflows

Backup Docker volume

Backup logs

Backup edited videos

---

# Recovery Strategy

If Docker crashes

Restart automatically.

If n8n crashes

Resume workflow.

If Upload fails

Retry.

If Download fails

Retry.

---

# Performance Goals

Download

<30 seconds

Editing

<60 seconds

Upload

<60 seconds

Entire pipeline

<3 minutes

---

# Coding Standards

One workflow

One responsibility.

No duplicated logic.

No hardcoded paths.

Every workflow documented.

Every API documented.

Every failure handled.

---

# Acceptance Criteria

Architecture is accepted when

✓ Services communicate correctly

✓ Docker persists data

✓ Modules are independent

✓ APIs authenticate successfully

✓ Storage structure remains organized

✓ Failures are logged

✓ Workflows restart safely

✓ Components can be replaced independently

---

End of Document

# AI Shorts Factory
# 03_Workflow_Specification.md
Version: 1.0

---

# Purpose

This document defines every workflow in the project.

Every workflow should perform exactly one responsibility.

The workflows must be modular.

No workflow should depend on implementation details of another workflow.

---

# MASTER WORKFLOW

```
Scheduler

↓

Content Finder

↓

Downloader

↓

Editor

↓

Metadata Generator

↓

Thumbnail Generator

↓

Uploader

↓

Logger

↓

Archive
```

---

# Workflow 1

## Content Finder

Purpose

Find licensed reusable videos.

Current Sources

- Pexels
- Pixabay (Future)

Inputs

Topic

Examples

Nature

Waterfall

Ocean

Rain

Forest

Sky

Animals

Relaxing

Output

JSON

Example

```
{
 video_url:"",
 duration:20,
 width:1080,
 height:1920
}
```

Validation

Must be

Portrait preferred

Minimum

1080x1920

Duration

10–60 seconds

If multiple videos exist

Rank by

Resolution

Duration

Popularity

Newest

Error Handling

No videos found

↓

Retry

↓

Next keyword

↓

Fail

Acceptance

One valid downloadable video returned.

---

# Workflow 2

Downloader

Purpose

Download video.

Input

Video URL

Output

downloads/video.mp4

Requirements

Preserve original quality.

Retry

3 times.

Log

Download size

Download duration

Source URL

Error Handling

Connection timeout

Retry

404

Skip

403

Skip

Acceptance

Playable MP4 stored.

---

# Workflow 3

Video Validator

Purpose

Validate downloaded file.

Checks

Exists

Playable

Resolution

Codec

Duration

Orientation

Reject

Corrupted files

Tiny files

Wrong orientation

Wrong codec

Output

PASS

or

FAIL

---

# Workflow 4

Video Editor

Purpose

Prepare YouTube Short.

Operations

Trim

Crop

Resize

Center

Zoom

Audio normalize

Optional blur

Optional fade

FFmpeg Commands

Resize

```
scale=1080:1920
```

Trim

```
-t 30
```

Audio

```
-loudnorm
```

Output

edited/final.mp4

Acceptance

Playable

9:16

MP4

Correct duration

---

# Workflow 5

Caption Generator

Purpose

Generate captions.

Current Version

Optional

Future

Whisper

Speech-to-text

Outputs

SRT

ASS

Burned captions

---

# Workflow 6

Background Music

Purpose

Attach royalty-free music.

Requirements

Volume ducking

Fade in

Fade out

Normalize

Future

Random music selection

---

# Workflow 7

Metadata Generator

Purpose

Generate

Title

Description

Hashtags

Example

Title

Beautiful Waterfall Relaxation

Description

Relax and enjoy this stunning waterfall.

Hashtags

#nature

#waterfall

#relaxing

Requirements

Avoid clickbait.

Length

Title

<100 characters

Description

<5000 characters

---

# Workflow 8

Thumbnail Generator

Current

Optional

Future

Generate thumbnail automatically.

---

# Workflow 9

Uploader

Purpose

Upload Short.

Platform

YouTube

Requirements

OAuth

Retry

Schedule

Playlist

Visibility

Metadata

Output

Video ID

Upload URL

Status

---

# Workflow 10

Logger

Purpose

Maintain execution history.

Store

Timestamp

Workflow

Duration

Video Name

Upload Status

Errors

Retry Count

Store

CSV

or

SQLite

Future

Dashboard

---

# Workflow 11

Archive

Purpose

Move processed files.

Folders

downloads/

↓

archive/

edited/

↓

archive/

Never overwrite originals.

---

# Scheduler

Current

Manual Trigger

Future

Cron

Every day

09:00

or

User configurable

---

# Retry Logic

Every workflow

Maximum retries

3

Wait

5 seconds

10 seconds

20 seconds

Then fail.

---

# Failure Policy

Downloader fails

↓

Skip

Editor fails

↓

Keep original

Uploader fails

↓

Retry

Logger fails

↓

Continue

Never stop entire pipeline because of one video.

---

# Workflow Dependencies

```
Content Finder

↓

Downloader

↓

Validator

↓

Editor

↓

Metadata

↓

Uploader

↓

Logger

↓

Archive
```

Each workflow only communicates through defined inputs and outputs.

No workflow should modify another workflow directly.

---

# Testing

Every workflow must pass

Unit Test

Integration Test

Failure Test

Performance Test

Recovery Test

---

# Acceptance Criteria

Every workflow is accepted when

✓ Input validated

✓ Output generated

✓ Errors handled

✓ Logs written

✓ Retry works

✓ Execution documented

---

# Future Workflows

Trend Detector

Analytics Collector

Performance Optimizer

Thumbnail AI

Voice Generator

Comment Monitor

Community Post Generator

A/B Testing

Automatic Scheduling Optimizer

Multi-Channel Publisher

---

# Development Rule

Never build one giant workflow.

Instead

Small workflows

↓

Reusable

↓

Maintainable

↓

Replaceable

↓

Scalable

---

END OF DOCUMENT

# AI Shorts Factory
# 04_Development_Guide.md
Version: 1.0

---

# Purpose

This document defines how the project should be developed.

It acts as the engineering handbook for both human developers and AI coding agents.

Every implementation must follow this guide.

---

# Development Philosophy

The project must be

- Modular
- Testable
- Maintainable
- Replaceable
- Documented

Never sacrifice architecture for speed.

---

# Development Order

## Phase 1

Infrastructure

Tasks

- Docker
- Docker Compose
- Git Repository
- Folder Structure
- Environment Variables
- n8n
- FFmpeg

Acceptance

Everything starts with one command.

---

## Phase 2

API Integration

Tasks

Pexels API

Pixabay API

YouTube OAuth

Acceptance

Authentication succeeds.

---

## Phase 3

Downloader

Tasks

Search

Rank

Download

Validate

Acceptance

One licensed MP4 saved locally.

---

## Phase 4

Editor

Tasks

Trim

Resize

Crop

Normalize

Music

Export

Acceptance

Playable Short generated.

---

## Phase 5

Metadata

Tasks

Title

Description

Hashtags

Acceptance

Metadata generated automatically.

---

## Phase 6

Uploader

Tasks

OAuth

Upload

Visibility

Playlist

Scheduling

Acceptance

Video appears on channel.

---

## Phase 7

Analytics

Tasks

History

Logging

Retry

Monitoring

Acceptance

Every execution recorded.

---

# Git Repository

Structure

```

main

develop

feature/\*

hotfix/\*

```

Rules

Never develop on main.

Merge only after testing.

---

# Commit Messages

Examples

```

feat: add downloader workflow

fix: retry logic

docs: update workflow specification

refactor: split editor module

test: uploader integration

```

---

# Docker

Every service runs inside Docker.

Never install runtime dependencies globally.

Containers

n8n

FFmpeg

Python

Future

Database

Monitoring

---

# Environment Variables

Store inside

.env

Required

```

PEXELS_API_KEY=

PIXABAY_API_KEY=

YOUTUBE_CLIENT_ID=

YOUTUBE_CLIENT_SECRET=

YOUTUBE_REFRESH_TOKEN=

DOWNLOAD_PATH=

EDIT_PATH=

LOG_PATH=

```

Never hardcode credentials.

Never commit .env.

---

# Folder Rules

downloads/

Raw videos only.

edited/

Final exported videos only.

archive/

Processed videos only.

logs/

Text

CSV

SQLite

scripts/

Python only.

ffmpeg/

Shell scripts only.

prompts/

Prompt templates only.

---

# Workflow Naming

Always use

```

01_Content_Finder

02_Downloader

03_Validator

04_Editor

05_Metadata

06_Uploader

07_Logger

```

Never use generic names.

---

# File Naming

Raw

```

raw_YYYYMMDD_HHMMSS.mp4

```

Edited

```

short_YYYYMMDD_HHMMSS.mp4

```

Logs

```

YYYYMMDD.log

```

---

# Coding Standards

Python

PEP8

Shell

POSIX

Markdown

GitHub Flavored Markdown

JSON

Pretty formatted

Indentation

4 spaces

---

# Error Handling

Never ignore exceptions.

Always log.

Always retry where appropriate.

Never silently fail.

---

# Retry Policy

API

3 retries

Network

3 retries

Upload

3 retries

Download

3 retries

Validation

No retry

---

# Logging Standard

Every workflow logs

Timestamp

Workflow

Status

Execution Time

Retry Count

Error Message

Video Name

Output

CSV

SQLite

---

# Security Rules

Never expose

API Keys

OAuth Tokens

Passwords

Secrets

Never print secrets.

Never upload secrets to GitHub.

---

# Testing Strategy

Every module requires

Unit Test

Integration Test

Failure Test

Performance Test

Recovery Test

---

# Unit Tests

Downloader

Can download

Validator

Can validate

Editor

Can export

Uploader

Can upload

Logger

Can log

---

# Integration Tests

Entire pipeline

Downloader

↓

Editor

↓

Uploader

↓

Logger

---

# Failure Tests

Disconnect Internet

Invalid API

Invalid OAuth

Disk Full

Corrupted Video

Quota Exceeded

All failures must be handled.

---

# Performance Targets

Search

<10 sec

Download

<30 sec

Edit

<60 sec

Upload

<60 sec

Entire Pipeline

<3 minutes

---

# Documentation Rules

Every workflow must include

Purpose

Inputs

Outputs

Dependencies

Error Handling

Acceptance Criteria

Future Improvements

---

# Pull Request Checklist

✓ Tests pass

✓ Documentation updated

✓ No secrets committed

✓ Logs verified

✓ Docker works

✓ Workflows import successfully

---

# Release Checklist

Docker builds

n8n imports

APIs authenticate

Downloader works

Editor works

Uploader works

Logs generated

Backup created

---

# Deployment

Development

Local Docker

Production

Linux VPS

Docker Compose

Reverse Proxy

HTTPS

---

# Backup Strategy

Daily

Export n8n

Backup Docker Volume

Backup Logs

Backup Metadata

Weekly

GitHub Push

---

# Maintenance

Monthly

Update Docker Images

Rotate Logs

Check API Quotas

Review Failed Uploads

---

# Future Improvements

Monitoring Dashboard

Health Checks

Email Notifications

Discord Alerts

Telegram Alerts

AI-Based Error Diagnosis

Automatic Updates

---

# AI Coding Agent Instructions

If an AI agent is implementing this project, it must:

- Follow the module order.
- Never merge responsibilities.
- Keep workflows small.
- Generate reusable code.
- Add documentation for every module.
- Add logging for every action.
- Implement retries.
- Validate all inputs.
- Avoid hardcoded values.
- Keep secrets in environment variables.
- Write production-quality code, not prototypes.

---

# Acceptance Criteria

This guide is considered implemented when:

✓ Repository follows the structure.

✓ Docker starts successfully.

✓ Every workflow is modular.

✓ All APIs authenticate.

✓ Logs exist.

✓ Tests pass.

✓ Documentation is complete.

✓ Project can be rebuilt from GitHub alone.

---

END OF DOCUMENT

# AI Shorts Factory
# 05_Future_Roadmap.md
Version: 1.0

---

# Purpose

This document defines the long-term roadmap of AI Shorts Factory.

Version 1 is focused on creating a reliable YouTube Shorts automation pipeline using licensed content.

Future versions expand capabilities while preserving the same modular architecture.

---

# Vision

Transform AI Shorts Factory from a single-channel automation tool into a production-grade content engine capable of operating multiple YouTube channels with minimal human intervention.

Every new feature must integrate with the existing architecture without breaking existing workflows.

---

# Guiding Principles

Always prioritize:

- Stability
- Reliability
- Automation
- Maintainability
- Low operational cost
- Legal use of licensed or original content

Never sacrifice reliability for additional features.

---

# Version 1 (MVP)

Goal

Produce one complete YouTube Short automatically.

Features

✓ Docker

✓ n8n

✓ Folder Structure

✓ Pexels API

✓ Downloader

✓ Validator

✓ FFmpeg Editing

✓ Metadata Generator

✓ YouTube Upload

✓ Logging

✓ Scheduler

Acceptance

One workflow executes successfully from start to finish.

---

# Version 2

Goal

Improve video quality.

New Features

Automatic intro

Automatic outro

Better transitions

Fade effects

Music library

Watermark support

Overlay images

Brand logo

Animated captions

Acceptance

Videos become visually consistent.

---

# Version 3

Goal

Improve content quality.

Features

Multiple licensed sources

Pexels

Pixabay

Coverr

Mixkit (manual/allowed integration)

Video ranking

Duplicate detection

Clip quality scoring

Acceptance

System consistently selects higher-quality clips.

---

# Version 4

Goal

Improve metadata.

Features

Better titles

Better descriptions

Keyword optimization

Automatic hashtags

Playlist assignment

Automatic upload scheduling

Acceptance

Metadata requires little or no manual editing.

---

# Version 5

Goal

Analytics.

Collect

Views

Likes

Comments

CTR

Retention

Upload history

Failures

Generate

Daily reports

Weekly reports

Monthly reports

Acceptance

Performance dashboard available.

---

# Version 6

Goal

Multiple Channels.

Examples

Nature

Animals

Relaxation

Space

Technology

Travel

Architecture

Each channel

Own schedule

Own metadata

Own playlists

Own branding

Acceptance

Multiple channels operate independently.

---

# Version 7

Goal

Optimization.

Features

Automatic retry improvements

Storage cleanup

Duplicate removal

Workflow optimization

Performance monitoring

Acceptance

Lower execution time.

---

# Version 8

Goal

Content Intelligence.

Possible Features

Trend detection

Topic suggestions

Content scoring

Performance prediction

Automatic niche analysis

These features should remain optional and configurable.

---

# Version 9

Goal

Developer Experience.

Features

Web dashboard

Workflow editor

Settings page

Statistics

Logs

Import/Export

Configuration wizard

Acceptance

Project becomes easier to manage.

---

# Version 10

Goal

Enterprise Readiness.

Features

Multiple users

Role-based access

Remote deployment

Cloud support

Monitoring

Centralized logs

Automatic updates

Plugin system

Acceptance

Project can support multiple deployments.

---

# Future Integrations

Possible future services

Google Drive

Dropbox

OneDrive

Telegram

Discord

Slack

Notion

GitHub Actions

Cloud Storage

These integrations should remain optional.

---

# Performance Goals

Average execution

<3 minutes

Download

<30 seconds

Editing

<60 seconds

Upload

<60 seconds

Failure recovery

<2 minutes

---

# Reliability Goals

Workflow success rate

>95%

Automatic retries

Enabled

Crash recovery

Enabled

Persistent storage

Enabled

Workflow backups

Daily

---

# Maintenance Roadmap

Weekly

Review logs

Review failed uploads

Update dependencies

Monthly

Docker updates

API review

Storage cleanup

Quarterly

Architecture review

Performance improvements

Security audit

---

# Documentation Roadmap

Every release must update

Architecture

Workflow Specification

Development Guide

API documentation

README

Changelog

---

# Release Strategy

Development

↓

Testing

↓

Staging

↓

Production

Never deploy directly to production without testing.

---

# Success Metrics

Technical

✓ Stable execution

✓ Modular workflows

✓ Reliable uploads

✓ Error recovery

Operational

✓ Minimal manual work

✓ Consistent publishing

✓ Low maintenance

Project

✓ Easy onboarding

✓ Good documentation

✓ Reproducible setup

---

# Long-Term Objectives

The project should always remain:

- Modular
- Easy to extend
- Docker-based
- Version controlled
- Documented
- Maintainable

Future features should be added as new modules rather than modifying existing ones whenever possible.

---

# AI Coding Agent Instructions

When implementing future versions:

1. Preserve backward compatibility.
2. Never remove working modules without replacement.
3. Prefer configuration over hardcoded values.
4. Keep workflows independent.
5. Document every new feature.
6. Add automated tests where practical.
7. Log all failures and retries.
8. Keep the project runnable with a single Docker Compose setup.

---

# Final Definition of Done

AI Shorts Factory Version 1 is complete when:

✓ One command starts Docker.

✓ n8n loads successfully.

✓ APIs authenticate.

✓ Licensed content is discovered.

✓ Video downloads successfully.

✓ Video is validated.

✓ FFmpeg processes the video.

✓ Metadata is generated.

✓ Video uploads to YouTube Shorts.

✓ Logs are written.

✓ Scheduler can execute automatically.

✓ Data persists after restart.

✓ Documentation is complete.

---

# End of Roadmap

This roadmap is intended to evolve over time. New features should be added without compromising the project's core principles of modularity, reliability, maintainability, and low-cost operation.