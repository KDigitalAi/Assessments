# Vercel Deployment Setup Guide

## 🔧 Required Environment Variables

To fix the "Error loading courses" issue on Vercel, you **MUST** set these environment variables in your Vercel project:

### Step 1: Go to Vercel Dashboard
1. Navigate to [Vercel Dashboard](https://vercel.com/dashboard)
2. Select your project: `assessments-gray`
3. Go to **Settings** → **Environment Variables**

### Step 2: Add Required Variables

Add the following environment variables:

#### 1. Supabase Configuration
```
SUPABASE_URL=https://your-project-id.supabase.co
SUPABASE_KEY=your-anon-public-key-here
```

**How to get these values:**
- Go to your [Supabase Dashboard](https://app.supabase.com)
- Select your project
- Go to **Settings** → **API**
- Copy:
  - **Project URL** → Use for `SUPABASE_URL`
  - **anon public** key → Use for `SUPABASE_KEY`

#### 2. OpenAI Configuration (Optional but recommended)
```
OPENAI_API_KEY=sk-your-openai-api-key-here
```

**How to get this:**
- Go to [OpenAI API Keys](https://platform.openai.com/api-keys)
- Create a new secret key
- Copy and paste it

#### 3. Application Settings
```
DEBUG=False
```

### Step 3: Apply to All Environments
- ✅ **Production**
- ✅ **Preview** 
- ✅ **Development**

### Step 4: Redeploy
After adding environment variables:
1. Go to **Deployments** tab
2. Click **Redeploy** on the latest deployment
3. Or push a new commit to trigger automatic deployment

## 🔍 Verify Environment Variables

After deployment, check the health endpoint:
```
https://assessments-gray.vercel.app/health
```

Look for:
- `"url_configured": true`
- `"key_configured": true`
- `"status": "connected"` in supabase checks

## 🛡️ Supabase Row Level Security (RLS) Setup

If you're still getting errors after setting environment variables, you may need to configure RLS policies:

### Required RLS Policies

Run these SQL commands in your Supabase SQL Editor:

```sql
-- Allow public SELECT on courses table
CREATE POLICY "Allow public read access to courses"
ON courses FOR SELECT
USING (true);

-- Allow public SELECT on assessments table
CREATE POLICY "Allow public read access to assessments"
ON assessments FOR SELECT
USING (status = 'published');

-- Allow public SELECT on skill_assessment_questions table
CREATE POLICY "Allow public read access to questions"
ON skill_assessment_questions FOR SELECT
USING (true);

-- Allow public SELECT on attempts table (for viewing results)
CREATE POLICY "Allow public read access to attempts"
ON attempts FOR SELECT
USING (true);

-- Allow public SELECT on results table
CREATE POLICY "Allow public read access to results"
ON results FOR SELECT
USING (true);

-- Allow public SELECT on responses table
CREATE POLICY "Allow public read access to responses"
ON responses FOR SELECT
USING (true);
```

### Enable RLS on Tables

```sql
-- Enable RLS on all tables
ALTER TABLE courses ENABLE ROW LEVEL SECURITY;
ALTER TABLE assessments ENABLE ROW LEVEL SECURITY;
ALTER TABLE skill_assessment_questions ENABLE ROW LEVEL SECURITY;
ALTER TABLE attempts ENABLE ROW LEVEL SECURITY;
ALTER TABLE results ENABLE ROW LEVEL SECURITY;
ALTER TABLE responses ENABLE ROW LEVEL SECURITY;
```

## ✅ Verification Checklist

- [ ] `SUPABASE_URL` is set in Vercel environment variables
- [ ] `SUPABASE_KEY` is set in Vercel environment variables
- [ ] Environment variables are applied to Production, Preview, and Development
- [ ] Application has been redeployed after setting variables
- [ ] Health check endpoint shows `"url_configured": true` and `"key_configured": true`
- [ ] RLS policies are configured in Supabase (if RLS is enabled)
- [ ] Browser console shows no CORS errors
- [ ] Network tab shows successful API calls to `/api/getAssessments`

## 🐛 Troubleshooting

### Issue: "Database service unavailable"
**Solution:** Check that `SUPABASE_URL` and `SUPABASE_KEY` are set correctly in Vercel

### Issue: "Permission denied" or "Row-level security"
**Solution:** Configure RLS policies as shown above, or disable RLS temporarily for testing

### Issue: "Error loading courses" still appears
**Solution:** 
1. Check Vercel function logs for detailed error messages
2. Verify environment variables are set (check `/health` endpoint)
3. Check browser console for CORS or network errors
4. Verify Supabase tables exist and have data

### Issue: CORS errors in browser
**Solution:** CORS is already configured to allow all origins on Vercel. If you still see CORS errors, check:
- Browser console for specific error messages
- Network tab to see if requests are reaching the server
- Vercel function logs for any errors

## 📞 Need Help?

If issues persist:
1. Check Vercel function logs: **Vercel Dashboard** → **Deployments** → **Functions** → **View Logs**
2. Check browser console for JavaScript errors
3. Check Network tab for failed API requests
4. Verify all environment variables are set correctly

