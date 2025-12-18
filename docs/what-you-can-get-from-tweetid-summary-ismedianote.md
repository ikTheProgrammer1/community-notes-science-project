# What You Can Retrieve From `tweetId`, `summary` Text, and `isMediaNote`

This note maps the minimal fields you might start with (post/tweet ID, note summary text, media flag) to the data you can pull from the X API v2 endpoints documented in this directory.

## Quick Map
- `tweetId` (aka `post_id`): lets you fetch the full tweet object, author, media/polls/places, metrics, safety flags, related tweets (replies/quotes/retweets), and user details.
- `summary` text (note body): lets you evaluate the note and search for matching/related tweets or notes.
- `isMediaNote`: tells you the note targets attached media; use it to request media expansions/fields for the tweet.

## Starting From `tweetId`
- **Tweet body & metadata**: `GET /2/tweets/{id}` (see `x-api-get-post-by-id.md`) returns text, created_at, lang, conversation_id, author_id, entities (mentions/urls/hashtags), context_annotations, reply_settings, edit history, note_tweet, scopes, card_uri.
- **Engagement & safety**: include `public_metrics`, `organic_metrics`/`non_public_metrics`/`promoted_metrics` (when authorized), `possibly_sensitive`, `withheld`.
- **Media & polls**: use `expansions=attachments.media_keys,attachments.poll_ids` with `media.fields` (alt_text, type, url/variants, dimensions, duration_ms, media_key, metrics) and `poll.fields` (options, end_datetime, duration_minutes, voting_status, id).
- **Places & topics**: `expansions=geo.place_id` with `place.fields` (name, full_name, country_code, geo shapes) plus `context_annotations` and `topics` when present.
- **Referenced tweets & threads**: `referenced_tweets` (retweeted/quoted/replied_to IDs) and `conversation_id` let you fetch the parent thread or quoted tweet via another `GET /2/tweets/{id}` call; `x-api-get-qupted-posts.md` covers `GET /2/tweets/{id}/quote_tweets` to list quotes.
- **Author profile**: from `author_id`, call `GET /2/users/{id}` (`x-api-get-user-by-id.md`) to retrieve username, name, verification, bio, profile images, location, urls, public_metrics, affiliations, and related metadata; you can also fetch liked posts, mentions, etc. (`x-api-get-liked-posts.md`, `x-api-get-mentions.md`).
- **Discovery**: search for the tweet or related content via `x-api-search-recent-posts.md` or `x-api-search-all-endpoint.md` using the ID or text; stream it via `x-api-stream-filtered-posts.md`.

## Starting From `summary` Text (note body)
- **Note quality scoring**: `POST /2/evaluate_note` (`x-api-evaluate-note.md`) with `note_text` + `post_id` returns a `claim_opinion_score`.
- **Find matching tweets**: use `search/recent` or `search/all` with keywords from the summary to surface the referenced tweet or similar posts; add expansions/fields to pull media, author, metrics, etc.
- **Find related notes**: filter `x-api-search-communitynotes-written.md` or `x-api-search-posts-eligible-for-community-notes.md` by text snippets (where supported) to locate other notes touching the same claims/posts for cross-reference.

## Using `isMediaNote`
- When true, the note targets attached media (image/video/GIF). Use this to:
  - Request `attachments.media_keys` expansion and rich `media.fields` to fetch media type, URLs/variants, dimensions, alt_text, and media-level metrics.
  - If video/GIF, inspect `variants` for bitrate/content_type; if image, use `url`, `height`, `width`, `alt_text`.
  - Pair media with the base tweet text to understand the full claim the note is addressing.

## Putting It Together
- With `tweetId` + `summary` + `isMediaNote`, you can assemble: the full tweet payload, author profile, engagement and safety signals, attachments (media/polls/places), conversation context (parents, replies, quotes), plus a quality score for the note text and cross-referenced notes/posts for the same claim. Use the documented field/expansion lists in the endpoint-specific files (e.g., `x-api-get-post-by-id.md`, `x-api-search-recent-posts.md`, `x-api-evaluate-note.md`) to request only what you need.
