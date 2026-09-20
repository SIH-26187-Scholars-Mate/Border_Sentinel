// src/api/supabaseClient.js
// Direct browser client used only for the two things the FastAPI backend
// does not proxy: account creation (signUp) and Google OAuth.
//
// Tokens this client produces are ordinary Supabase-issued JWTs — the same
// kind POST /auth/login already hands back for email+password. The backend
// verifies any such token via Supabase's JWKS endpoint (see
// backend/app/core/security.py) without caring how it was obtained, so once
// we have a session here we feed its access_token into AuthContext exactly
// like the existing login() flow does.
import { createClient } from '@supabase/supabase-js'

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY

if (!supabaseUrl || !supabaseAnonKey) {
  // eslint-disable-next-line no-console
  console.warn(
    'VITE_SUPABASE_URL / VITE_SUPABASE_ANON_KEY are not set in frontend/.env — ' +
    'registration and "Continue with Google" will not work until they are added.'
  )
}

export const supabase = createClient(supabaseUrl ?? '', supabaseAnonKey ?? '')
