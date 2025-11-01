import os
import json
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import pandas as pd
import random

TOKEN_PATH = ".spotify_tokens.json"

def get_spotify_client():
    """Create a Spotipy client.

    Priority order:
    1. Use SPOTIFY_ACCESS_TOKEN env var (for GitHub Actions or other short-lived tokens).
    2. If available, use SPOTIFY_CLIENT_ID / SPOTIFY_CLIENT_SECRET / SPOTIFY_REFRESH_TOKEN / SPOTIFY_REDIRECT_URI
       from environment to refresh an access token.
    3. Fall back to the local `.spotify_tokens.json` refresh flow (original behaviour).
    """

    # 1) Direct access token provided (e.g. via GitHub Actions secrets)
    access_token = os.getenv("SPOTIFY_ACCESS_TOKEN")
    if access_token:
        return spotipy.Spotify(auth=access_token)

    # 2) Credentials & refresh token provided via environment variables
    client_id = os.getenv("SPOTIFY_CLIENT_ID")
    client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
    refresh_token = os.getenv("SPOTIFY_REFRESH_TOKEN")

    if client_id and client_secret and refresh_token and redirect_uri:
        sp_oauth = SpotifyOAuth(
            client_id=client_id,
            client_secret=client_secret,
            scope="playlist-modify-public playlist-modify-private",
        )
        token_info = sp_oauth.refresh_access_token(refresh_token)
        return spotipy.Spotify(auth=token_info["access_token"])

    # 3) Fallback to stored tokens file (existing local-dev flow)
    if not os.path.exists(TOKEN_PATH):
        raise FileNotFoundError(
            "No .spotify_tokens.json file found. Run spotify_auth.py first to authorise or set environment variables."
        )

    with open(TOKEN_PATH, "r") as f:
        data = json.load(f)

    sp_oauth = SpotifyOAuth(
        client_id=data["client_id"],
        client_secret=data["client_secret"],
        redirect_uri=data["redirect_uri"],
        scope="playlist-modify-public playlist-modify-private",
    )

    # Manually fetch new access token from stored refresh token
    token_info = sp_oauth.refresh_access_token(data["refresh_token"])
    sp = spotipy.Spotify(auth=token_info["access_token"])
    return sp


def create_playlist(sp, name, description="", public=False):
    """Create a new playlist under the authorised user’s account."""
    user_id = sp.me()["id"]
    playlist = sp.user_playlist_create(user=user_id, name=name, public=public, description=description)
    print(f"✅ Created playlist: {playlist['name']} ({playlist['external_urls']['spotify']})")
    return playlist["id"]


def add_tracks(sp, playlist_id, track_uris):
    """Add tracks to the given playlist."""
    if not track_uris:
        print("No tracks to add.")
        return
    sp.playlist_add_items(playlist_id, track_uris)
    print(f"🎵 Added {len(track_uris)} tracks to playlist.")


# Function to check if a playlist exists
def playlist_exists(sp, name):
    playlists = sp.current_user_playlists()
    while playlists:
        for playlist in playlists['items']:
            if playlist['name'] == name:
                return playlist['id']
        if playlists['next']:
            playlists = sp.next(playlists)
        else:
            playlists = None
    return None


# Function to replace tracks in a playlist
def replace_tracks(sp, playlist_id, track_uris):
    sp.playlist_replace_items(playlist_id, track_uris)
    print(f"🎵 Replaced tracks in playlist with ID: {playlist_id}.")


# Function to filter tracks based on play counts
def filter_tracks_by_play_count(csv_file):
    df = pd.read_csv(csv_file)
    tracks_to_add = []

    # Select 10 tracks with plays >= 10
    tracks_to_add.extend(df[df['plays'] >= 10].sample(n=10)['uri'].tolist())

    # Select 10 tracks with 5 <= plays < 10
    tracks_to_add.extend(df[(df['plays'] >= 5) & (df['plays'] < 10)].sample(n=10)['uri'].tolist())

    # Select 10 tracks with plays < 5
    tracks_to_add.extend(df[df['plays'] < 5].sample(n=10)['uri'].tolist())

    return tracks_to_add


# Function to create or update the Spotify playlist

def create_or_update_playlist(sp, user_id, playlist_name, csv_file):
    # Check if the playlist exists using the existing function
    playlist_id = playlist_exists(sp, playlist_name)

    # If the playlist does not exist, create it
    if not playlist_id:
        playlist = sp.user_playlist_create(user_id, playlist_name)
        playlist_id = playlist['id']

    # Get the tracks to add
    tracks_to_add = filter_tracks_by_play_count(csv_file)

    # Replace the existing tracks in the playlist
    replace_tracks(sp, playlist_id, tracks_to_add)


def main():
    sp = get_spotify_client()

    # Check for existing playlist
    playlist_name = "My time capsule"
    playlist_id = playlist_exists(sp, playlist_name)

    # If the playlist does not exist, create it
    if not playlist_id:
        description = "Abbie's time capsule playlist that automatically refreshes with a random selection of her old tracks every day."
        playlist_id = create_playlist(sp, playlist_name, description, public=False)
    else:
        print(f"✅ Found existing playlist: {playlist_name}")

    # Filter and select track URIs from CSV
    track_uris = filter_tracks_by_play_count('final_filtered_tracks_with_uri.csv')

    # Replace tracks in the playlist
    replace_tracks(sp, playlist_id, track_uris)

    print("✅ Playlist update complete. Listen to it here: https://open.spotify.com/playlist/" + playlist_id)


if __name__ == "__main__":
    main()