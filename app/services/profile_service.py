"""
Service for managing user profiles - simplified for single test user
"""

from typing import Optional
from uuid import UUID
from app.services.supabase_service import supabase_service
from app.utils.logger import logger

# Hardcoded test user identifier for Skill Capital
TEST_USER_EMAIL = "test_user@skillcapital.ai"
TEST_USER_NAME = "Skill Capital Test User"
TEST_USER_ROLE = "student"


def ensure_default_test_user() -> Optional[UUID]:
    """
    Ensure the single default test user profile exists in the database.
    This is the ONLY user used for all Skill Assessment operations.
    
    Strategy:
    1. Check for test user by email (test_user@skillcapital.ai)
    2. If found, return its UUID
    3. If not found, try to create it using an existing auth.user ID
    4. If creation fails, try to use any existing profile as fallback
    
    Returns:
        UUID of the test user profile, or None if creation failed
    """
    try:
        client = supabase_service.get_client()
        if not client:
            logger.error("❌ Supabase client not available. Cannot access test user.")
            return None
        
        # Step 1: Check if test user already exists by email
        try:
            test_user_response = client.table("profiles")\
                .select("id, email, full_name")\
                .eq("email", TEST_USER_EMAIL)\
                .limit(1)\
                .execute()
            
            if test_user_response.data and len(test_user_response.data) > 0:
                profile_id = test_user_response.data[0].get("id")
                success_msg = f"✅ Test user already exists in Supabase: {TEST_USER_EMAIL} (ID: {profile_id})"
                logger.info(success_msg)
                print(success_msg)  # Also print to console as requested
                # Verify the record exists by fetching again
                verify_response = client.table("profiles")\
                    .select("*")\
                    .eq("email", TEST_USER_EMAIL)\
                    .limit(1)\
                    .execute()
                if verify_response.data:
                    logger.info(f"✅ Verification: Test user confirmed in database with email={verify_response.data[0].get('email')}, role={verify_response.data[0].get('role')}")
                return UUID(profile_id) if profile_id else None
        except Exception as e:
            logger.warning(f"⚠️  Error checking for test user: {str(e)}")
        
        # Step 2: Test user doesn't exist - try to create it
        logger.info(f"🔄 Test user not found. Creating default test user: {TEST_USER_EMAIL}")
        
        # Strategy: Use SQL to create the profile using any existing auth.user ID
        # This bypasses the need to know the auth.user ID upfront
        try:
            # Strategy 1: Try to create via SQL using any existing auth.user ID
            # This SQL will use any existing auth.user ID from auth.users table
            sql_insert = f"""
                INSERT INTO profiles (id, email, full_name, role, organization)
                SELECT 
                    id,
                    '{TEST_USER_EMAIL}',
                    '{TEST_USER_NAME}',
                    '{TEST_USER_ROLE}',
                    'Skill Capital'
                FROM auth.users
                WHERE id NOT IN (SELECT id FROM profiles WHERE id IS NOT NULL)
                LIMIT 1
                ON CONFLICT (id) DO UPDATE
                SET email = EXCLUDED.email,
                    full_name = EXCLUDED.full_name,
                    role = EXCLUDED.role,
                    organization = EXCLUDED.organization
                RETURNING id;
            """
            
            # Try to execute SQL via RPC (requires a custom function in Supabase)
            # If that doesn't work, we'll try the direct insert method below
            try:
                # Note: This requires a custom RPC function in Supabase
                # For now, we'll skip this and use direct insert
                pass
            except Exception:
                pass
            
            # Strategy 2: Try to get any existing auth.user ID from existing profiles
            # Since profiles.id references auth.users.id, existing profile IDs are valid auth.user IDs
            existing_profiles = client.table("profiles").select("id").limit(1).execute()
            auth_user_id = None
            
            if existing_profiles.data and len(existing_profiles.data) > 0:
                # Use existing profile's ID (which is already a valid auth.user ID)
                auth_user_id = existing_profiles.data[0].get("id")
                logger.info(f"Found existing profile with auth.user ID: {auth_user_id}")
            else:
                # Profiles table is empty - try to get auth.user ID via RPC or SQL
                logger.info("Profiles table is empty. Attempting to find auth.user ID...")
                
                # Try to use RPC to create test user profile automatically
                # Strategy: Try to call a Supabase RPC function that can access auth.users
                try:
                    # Try RPC function that creates test user profile
                    # This requires create_test_user_rpc.sql to be run in Supabase first
                    rpc_result = client.rpc(
                        "create_test_user_profile",
                        {
                            "p_email": TEST_USER_EMAIL,
                            "p_full_name": TEST_USER_NAME,
                            "p_role": TEST_USER_ROLE,
                            "p_organization": "Skill Capital"
                        }
                    ).execute()
                    
                    if rpc_result.data:
                        # Function returns profile data
                        profile_data = rpc_result.data[0] if isinstance(rpc_result.data, list) else rpc_result.data
                        if profile_data:
                            auth_user_id = profile_data.get("id")
                            if auth_user_id:
                                logger.info(f"✅ Created test user via RPC function: {auth_user_id}")
                                logger.info(f"✅ Test user profile created successfully in Supabase")
                                print("✅ Test user profile created successfully in Supabase.")
                                # Verify and return
                                verify_response = client.table("profiles")\
                                    .select("*")\
                                    .eq("email", TEST_USER_EMAIL)\
                                    .limit(1)\
                                    .execute()
                                if verify_response.data:
                                    profile_id = verify_response.data[0].get("id")
                                    return UUID(profile_id) if profile_id else None
                except Exception as rpc_error:
                    # RPC function doesn't exist - that's okay, continue with SQL approach
                    logger.debug(f"RPC create_test_user_profile not available: {str(rpc_error)}")
                    logger.debug("   To enable automatic creation, run app/models/create_test_user_rpc.sql in Supabase")
                    auth_user_id = None
                
                # If we still don't have auth_user_id, provide clear instructions
                if not auth_user_id:
                    logger.warning("⚠️  Profiles table is empty. Cannot auto-create profile without auth.user ID.")
                    logger.warning("   SOLUTION: Run this SQL in Supabase SQL Editor (SQL Editor > New Query):")
                    logger.warning("")
                    logger.warning("   INSERT INTO profiles (id, email, full_name, role, organization)")
                    logger.warning(f"   SELECT id, '{TEST_USER_EMAIL}', '{TEST_USER_NAME}', '{TEST_USER_ROLE}', 'Skill Capital'")
                    logger.warning("   FROM auth.users")
                    logger.warning("   WHERE id NOT IN (SELECT id FROM profiles WHERE id IS NOT NULL)")
                    logger.warning("   LIMIT 1")
                    logger.warning("   ON CONFLICT (id) DO UPDATE")
                    logger.warning("   SET email = EXCLUDED.email,")
                    logger.warning("       full_name = EXCLUDED.full_name,")
                    logger.warning("       role = EXCLUDED.role,")
                    logger.warning("       organization = EXCLUDED.organization;")
                    logger.warning("")
                    logger.warning("   Or use the provided SQL file: create_test_user.sql")
                    logger.warning("")
                    
                    # If auth.users might be empty, provide instructions to create auth.user first
                    logger.warning("   NOTE: If auth.users is also empty, create an auth user first:")
                    logger.warning("   1. Go to Supabase Dashboard > Authentication > Users")
                    logger.warning("   2. Click 'Add user' or 'Invite user'")
                    logger.warning("   3. Create a user (email doesn't matter for test user)")
                    logger.warning("   4. Then run the SQL above")
                    
                    return None
            
            # Only proceed if we have auth_user_id
            if not auth_user_id:
                return None
            
            # Try to insert the test user profile with the auth_user_id
            test_profile_data = {
                "id": str(auth_user_id),
                "email": TEST_USER_EMAIL,
                "full_name": TEST_USER_NAME,
                "role": TEST_USER_ROLE,
                "organization": "Skill Capital"
            }
            
            try:
                profile_response = client.table("profiles").insert(test_profile_data).execute()
                if profile_response.data and len(profile_response.data) > 0:
                    profile_id = UUID(profile_response.data[0].get("id"))
                    logger.info(f"✅ Created test user profile: {profile_id}")
                    
                    # Verify the creation by fetching again
                    verify_response = client.table("profiles")\
                        .select("*")\
                        .eq("email", TEST_USER_EMAIL)\
                        .limit(1)\
                        .execute()
                    
                    if verify_response.data and len(verify_response.data) > 0:
                        profile_data = verify_response.data[0]
                        success_msg = f"✅ Default test user created successfully in Supabase"
                        logger.info(success_msg)
                        print(success_msg)  # Also print to console as requested
                        logger.info(f"   Email: {profile_data.get('email')}")
                        logger.info(f"   Full Name: {profile_data.get('full_name')}")
                        logger.info(f"   Role: {profile_data.get('role')}")
                        logger.info(f"   ID: {profile_data.get('id')}")
                        return profile_id
                    else:
                        logger.error("❌ Profile created but verification failed - profile not found in database")
                        return None
                        
            except Exception as insert_error:
                error_msg = str(insert_error).lower()
                if "unique" in error_msg or "duplicate" in error_msg or "conflict" in error_msg or "violates unique constraint" in error_msg:
                    # Profile might have been created by another request - try to fetch it again
                    logger.info("Profile may have been created by another process. Re-fetching...")
                    try:
                        test_user_response = client.table("profiles")\
                            .select("*")\
                            .eq("email", TEST_USER_EMAIL)\
                            .limit(1)\
                            .execute()
                        if test_user_response.data and len(test_user_response.data) > 0:
                            profile_id = test_user_response.data[0].get("id")
                            success_msg = f"✅ Test user already exists in Supabase: {TEST_USER_EMAIL}"
                            logger.info(success_msg)
                            print(success_msg)  # Also print to console as requested
                            return UUID(profile_id) if profile_id else None
                    except Exception:
                        pass
                
                logger.error(f"❌ Could not create test user: {str(insert_error)}")
                logger.error(f"   Error details: {type(insert_error).__name__}: {insert_error}")
                # Fall through to use existing profile as fallback
        except Exception as create_error:
            logger.warning(f"Could not create test user: {str(create_error)}")
            # Fall through to use existing profile
        
        # Fallback: Use any existing profile (if test user creation failed)
        try:
            existing_profiles = client.table("profiles").select("id").limit(1).execute()
            if existing_profiles.data and len(existing_profiles.data) > 0:
                profile_id = existing_profiles.data[0].get("id")
                logger.warning(f"⚠️  Using existing profile as fallback: {profile_id}")
                logger.warning(f"   Could not create test user. Please ensure auth.users has at least one user.")
                return UUID(profile_id) if profile_id else None
        except Exception as e:
            logger.error(f"❌ Could not get any existing profile: {str(e)}")
        
        # All strategies failed
        logger.error("❌ Failed to create or find test user profile")
        logger.error("   SOLUTION: Run this SQL in Supabase SQL Editor:")
        logger.error("   INSERT INTO profiles (id, email, full_name, role, organization)")
        logger.error("   SELECT id, 'test_user@skillcapital.ai', 'Skill Capital Test User', 'student', 'Skill Capital'")
        logger.error("   FROM auth.users WHERE id NOT IN (SELECT id FROM profiles) LIMIT 1")
        logger.error("   ON CONFLICT (id) DO NOTHING;")
        return None
        
    except Exception as e:
        logger.error(f"❌ Error in ensure_default_test_user: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return None


def get_test_user_id() -> Optional[UUID]:
    """
    Get the test user ID - always returns the same test user.
    This is the main function used throughout the application.
    
    Returns:
        UUID of the test user profile
    """
    return ensure_default_test_user()


def get_or_create_default_user() -> Optional[UUID]:
    """
    Alias for get_test_user_id() for backward compatibility.
    """
    return get_test_user_id()

