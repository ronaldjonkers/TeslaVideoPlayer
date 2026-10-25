# Plex subtitles

The interface is in English. Media titles, summaries, channel names and subtitle dialogue remain in their original language.

Choose **Settings → Preferred subtitle language**, then save. Each account has its own preference. **Off** disables automatic subtitles; **Plex default** follows the selected track or a forced track reported by Plex. A language preference chooses a matching supported track when opening a video. If none is available, subtitles remain off.

During Plex playback, use **Subtitles** to select a track or turn captions off. Changing a text track does not restart the audio or video. Captions follow the playback position after seeking, pausing and changing quality, and remain visible in fullscreen.

Text tracks are fetched through the authenticated application server and drawn as plain text over the canvas. SRT, WebVTT and ASS dialogue are supported. Styling and positioning from ASS are simplified. Plex converts other supported text formats when available. External subtitle files must already be indexed by Plex; this feature does not search for or download new subtitles.

Embedded PGS, VobSub and DVB bitmap tracks with a stream index are rendered into the image by FFmpeg. Switching to or from a bitmap track restarts playback at the current position and can require more CPU. External bitmap tracks and unknown formats are shown as unavailable. Plex access permissions and the server's ability to extract a track still apply.

Embedded text extraction selects the subtitle stream on the Plex media part before requesting Plex's subtitle conversion endpoint. Plex may remember that selection for the connected Plex account. Application preferences remain independent per Tesla Media account.

Verification uses isolated Plex fixtures for ownership, language preference persistence, external and embedded text retrieval, track switching and playback synchronization. It does not guarantee every Plex server version or subtitle file will convert successfully.
