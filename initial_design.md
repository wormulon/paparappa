I want to create a targeted script for the visually impaired to be able to watch media with subtitles.

Imagine an English speaking user who is visually impaired and cannot follow along subtitles. The idea would be to listen to the TTS of the subtitles as the characters speak. 

Someone had a similar idea, detailed in this reddit thread. I do not know if MPV is actually necessary for this to work. 
https://www.reddit.com/r/mpv/comments/15okyt1/how_to_set_up_texttospeech_tts_for_subtitles_in/


What I want is a script that takes a video file, parses the subtitle track into a TTS'd audio track that is then either merged or played at the same time as the original language audio track.

i.e. Instead of Japanese (Original) it's Japanese (English Subs, TTS Voice Johnny)

For the proof of concept, you point the script at an input file, determine the TTS voice, then it creates a new audio track that will be available when the user opens up the video file and looks for audio tracks. 

You must also specify the speed of TTS as well, ideally this could be done on the fly but my understanding of audio tracks is it has to be done ONCE, and if the mastering is poor it must be re-done. 

I believe the reddit poster has this hooked up to an AI voice model to TTS pipeline, that is not necessary for this proof of concept. 

For an actual release version, the user would drag the video file into a file box, and click the settings they want.

Take these posts as guidance as well:

POST 1 https://www.reddit.com/r/mpv/comments/15okyt1/how_to_set_up_texttospeech_tts_for_subtitles_in/jvupsyg/

POST 2
[–]Matty_Mroz[S] 1 point 12 months ago 

I ended up making a separate Python script that translates into my language, generates TTS from the movie subtitles, and merges it with the audio track. However, it doesn't work in real-time—processing 24 minutes of video takes anywhere from 30 seconds to 10 minutes, depending on the type of TTS used.
https://drive.google.com/file/d/1UvhB3oOWSJJokzMDAw3eQvfAIxbMSveN/view?usp=drive_link

Do not access the google drive link. It is a video file showing off the script.
