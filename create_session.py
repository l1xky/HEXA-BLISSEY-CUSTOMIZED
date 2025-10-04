import asyncio
import os
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError

async def create_session():
    print("session creator")
    
    # api (update these)
    API_ID = 1747534
    API_HASH = "5a2684512006853f2e48aca9652d83ea"
    
    # session name (update if want)
    SESSION_FILE = 'blissey_session'
    
    if os.path.exists(f'{SESSION_FILE}.session'):
        os.remove(f'{SESSION_FILE}.session')
        print("removed existing session file")
    
    try:
        client = TelegramClient(SESSION_FILE, API_ID, API_HASH)
        
        print("starting authentication...")
        await client.start()
        
        if await client.is_user_authorized():
            print("already authorized")
        else:
            print("authorization required")
            
            phone = input("enter your phone number (with country code): ").strip()
            if not phone:
                print("phone number required")
                return
            
            print("sending verification code...")
            await client.send_code_request(phone)
            
            code = input("enter verification code: ").strip()
            if not code:
                print("verification code required")
                return
            
            try:
                await client.sign_in(phone, code)
                print("successfully signed in")
            except SessionPasswordNeededError:
                print("2fa enabled")
                password = input("enter your 2fa password: ").strip()
                if not password:
                    print("2fa password required")
                    return
                await client.sign_in(password=password)
                print("successfully signed in with 2fa")
        
        me = await client.get_me()
        print(f"logged in as: {me.first_name} (@{me.username})")
        
        await client.disconnect()
        print("session saved successfully")
        
        if os.path.exists(f'{SESSION_FILE}.session'):
            print(f"session file created: {SESSION_FILE}.session")
            print("ready to use")
            print("next step: run 'python main.py'")
        else:
            print("session file was not created")
            
    except Exception as e:
        print(f"error: {e}")
        print("try running the script again")

if __name__ == "__main__":
    try:
        asyncio.run(create_session())
    except KeyboardInterrupt:
        print("cancelled by user")
    except Exception as e:
        print(f"error: {e}")
