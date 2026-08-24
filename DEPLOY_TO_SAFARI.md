# Put ScheduleAI on Safari with Render

This version is prepared for Render deployment.

## Fast path

1. Create a free GitHub account if you do not already have one.
2. Create a new GitHub repository named `scheduleai`.
3. Upload every file in this folder to that repository.
4. Go to Render and create a **Blueprint** from your GitHub repository.
5. Render will read `render.yaml` and create the web service.
6. After Render gives you a public URL, copy it. It will look similar to:
   `https://scheduleai-xxxx.onrender.com`
7. In Render, open the service's **Environment** settings and set:
   `APP_BASE_URL` = your exact Render URL
8. In Google Cloud Console, add this authorized redirect URI to your OAuth client:
   `https://YOUR-RENDER-URL.onrender.com/oauth2callback`
9. Add your Google OAuth credentials file as `client_secret.json` before deployment.

## Important security note

`client_secret.json` contains private credentials. For a real public app, do NOT keep it in a public GitHub repository.
Use a private repository or store the credentials securely as environment variables / secret files.

## Open it in Safari

Once deployed, paste the Render URL into Safari.

On iPhone:
Share button → **Add to Home Screen**

That makes ScheduleAI appear on your Home Screen like an app.

## If Google sign-in says "redirect_uri_mismatch"

Make sure these match exactly:
- Render `APP_BASE_URL`
- Google OAuth authorized redirect URI
- Your actual public Render URL

The callback must end with:
`/oauth2callback`
