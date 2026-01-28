import speech_recognition as sr
import tempfile
import os


class AudioInputHandler:
    def __init__(self):
        self.recognizer = sr.Recognizer()
        self.recognizer.energy_threshold = 4000
        self.recognizer.dynamic_energy_threshold = True
    
    def transcribe_audio_file(self, audio_file):
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_file:
                tmp_file.write(audio_file.read())
                tmp_path = tmp_file.name
            
            with sr.AudioFile(tmp_path) as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                audio_data = self.recognizer.record(source)
            
            text = self.recognizer.recognize_google(audio_data)
            return {"success": True, "text": text, "error": None}
        
        except sr.UnknownValueError:
            return {"success": False, "text": None, "error": "Could not understand the audio. Please speak clearly."}
        except sr.RequestError as e:
            return {"success": False, "text": None, "error": f"Speech recognition service error: {str(e)}"}
        except Exception as e:
            return {"success": False, "text": None, "error": f"Error processing audio: {str(e)}"}
        finally:
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except:
                    pass
    
    def transcribe_from_microphone(self, timeout=10, phrase_time_limit=30):
        try:
            with sr.Microphone() as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=1)
                audio_data = self.recognizer.listen(source, timeout=timeout, phrase_time_limit=phrase_time_limit)
            
            text = self.recognizer.recognize_google(audio_data)
            return {"success": True, "text": text, "error": None}
        
        except sr.WaitTimeoutError:
            return {"success": False, "text": None, "error": "No speech detected within timeout period."}
        except sr.UnknownValueError:
            return {"success": False, "text": None, "error": "Could not understand the audio."}
        except sr.RequestError as e:
            return {"success": False, "text": None, "error": f"Service error: {str(e)}"}
        except Exception as e:
            return {"success": False, "text": None, "error": f"Microphone error: {str(e)}"}


def process_text_input(text):
    if not text or not text.strip():
        return {"success": False, "text": None, "error": "Empty input provided."}
    
    cleaned_text = text.strip()
    return {"success": True, "text": cleaned_text, "error": None}
