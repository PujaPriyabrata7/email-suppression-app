from flask import Flask, request, send_file
import pandas as pd
import hashlib
import os
import tempfile

app = Flask(__name__)

def md5_hash(email):
    return hashlib.md5(email.strip().lower().encode()).hexdigest()

def load_suppression_list(suppression_file):
    ext = os.path.splitext(suppression_file.filename)[1].lower()
    suppression_emails = []

    if ext == '.csv':
        df = pd.read_csv(suppression_file)
        if 'email' not in df.columns:
            return None, "Suppression CSV must have 'email' column."
        suppression_emails = df['email'].dropna().astype(str).tolist()
    else:
        suppression_emails = [line.decode('utf-8').strip() for line in suppression_file if line.strip()]

    suppression_hashes = set()
    for entry in suppression_emails:
        # If already an md5 hash (32 hex chars), use directly
        if len(entry) == 32 and all(c in '0123456789abcdef' for c in entry.lower()):
            suppression_hashes.add(entry.lower())
        else:
            suppression_hashes.add(md5_hash(entry))
    return suppression_hashes, None

@app.route('/supp', methods=['GET', 'POST'])
def supp_tool():
    if request.method == 'POST':
        emails_file = request.files.get('emails')
        suppression_file = request.files.get('suppression')

        if not emails_file or not suppression_file:
            return "Both files are required!", 400

        suppression_hashes, error = load_suppression_list(suppression_file)
        if error:
            return error, 400

        ext = os.path.splitext(emails_file.filename)[1].lower()

        if ext == '.csv':
            df = pd.read_csv(emails_file)
            if 'email' not in df.columns:
                return "Emails CSV must have 'email' column.", 400
            emails = df['email'].dropna().astype(str).tolist()
        else:
            emails = [line.decode('utf-8').strip() for line in emails_file if line.strip()]

        df = pd.DataFrame(emails, columns=['email'])
        df['md5'] = df['email'].apply(md5_hash)

        clean_df = df[~df['md5'].isin(suppression_hashes)]
        suppressed_df = df[df['md5'].isin(suppression_hashes)]

        tmp_dir = tempfile.gettempdir()
        clean_path = os.path.join(tmp_dir, "clean_emails.txt")
        suppressed_path = os.path.join(tmp_dir, "suppressed_emails.txt")

        clean_df[['email']].to_csv(clean_path, index=False, header=False)
        suppressed_df[['email']].to_csv(suppressed_path, index=False, header=False)

        return f"""
            <h2>Results</h2>
            <p>Clean emails: {len(clean_df)}</p>
            <p>Suppressed emails: {len(suppressed_df)}</p>
            <a href="/download/clean">Download Clean Emails</a><br>
            <a href="/download/suppressed">Download Suppressed Emails</a><br><br>
            <a href="/supp">Try Again</a>
        """

    return '''
    <h2>Email Suppression Upload</h2>
    <form method="post" enctype="multipart/form-data">
      Email file (.txt or .csv): <input type="file" name="emails" required><br><br>
      Suppression file (.txt or .csv): <input type="file" name="suppression" required><br><br>
      <input type="submit" value="Submit">
    </form>
    '''

@app.route('/download/<file_type>')
def download(file_type):
    tmp_dir = tempfile.gettempdir()
    file_map = {
        'clean': os.path.join(tmp_dir, "clean_emails.txt"),
        'suppressed': os.path.join(tmp_dir, "suppressed_emails.txt")
    }
    path = file_map.get(file_type)
    if path and os.path.exists(path):
        return send_file(path, as_attachment=True)
    return "File not found", 404

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)