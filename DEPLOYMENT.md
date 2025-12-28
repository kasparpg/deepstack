# Web Deployment Guide

## Local Testing

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Run the web application:
```bash
python app.py
```

3. Open your browser to `http://localhost:5000`

## Deploy to Heroku

### Prerequisites
- Install [Heroku CLI](https://devcenter.heroku.com/articles/heroku-cli)
- Create a [Heroku account](https://signup.heroku.com/)

### Deployment Steps

1. **Login to Heroku**:
```bash
heroku login
```

2. **Create a new Heroku app**:
```bash
heroku create your-poker-app-name
```

3. **Set buildpacks** (for TensorFlow support):
```bash
heroku buildpacks:set heroku/python
```

4. **Configure environment variables**:
```bash
heroku config:set SECRET_KEY=$(python -c 'import secrets; print(secrets.token_hex(32))')
```

5. **Deploy to Heroku**:
```bash
git add .
git commit -m "Deploy to Heroku"
git push heroku main
```

6. **Open your app**:
```bash
heroku open
```

7. **View logs** (if needed):
```bash
heroku logs --tail
```

### Important Notes

- **Memory**: TensorFlow models require significant memory. You may need to upgrade from the free tier:
  ```bash
  heroku ps:scale web=1:standard-1x
  ```

- **Model Files**: The `models/` directory must be committed to git for deployment

- **Environment Variables**: Set `SECRET_KEY` in production for security

## Deploy to Render

1. Create a new account at [Render.com](https://render.com)

2. Click "New +" and select "Web Service"

3. Connect your GitHub repository

4. Configure:
   - **Name**: your-poker-app
   - **Environment**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn --worker-class eventlet -w 1 app:app`

5. Add environment variable:
   - Key: `SECRET_KEY`
   - Value: (generate a random secret)

6. Click "Create Web Service"

## Deploy to Railway

1. Create account at [Railway.app](https://railway.app)

2. Click "New Project" → "Deploy from GitHub repo"

3. Select your repository

4. Railway will auto-detect Python and deploy

5. Add environment variables in Settings:
   - `SECRET_KEY`: (your secret key)

## Deploy to AWS (EC2)

1. **Launch EC2 instance**:
   - Choose Ubuntu 22.04 LTS
   - Select t2.medium or larger (for TensorFlow)
   - Configure security group (allow ports 22, 80, 443)

2. **SSH into instance**:
```bash
ssh -i your-key.pem ubuntu@your-instance-ip
```

3. **Install dependencies**:
```bash
sudo apt update
sudo apt install python3-pip python3-venv nginx -y
```

4. **Clone repository**:
```bash
git clone your-repo-url
cd deepstack2
```

5. **Setup virtual environment**:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

6. **Configure Nginx**:
```bash
sudo nano /etc/nginx/sites-available/poker
```

Add:
```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }
}
```

Enable site:
```bash
sudo ln -s /etc/nginx/sites-available/poker /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

7. **Run with systemd**:
Create `/etc/systemd/system/poker.service`:
```ini
[Unit]
Description=Poker Web App
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/deepstack2
Environment="PATH=/home/ubuntu/deepstack2/.venv/bin"
ExecStart=/home/ubuntu/deepstack2/.venv/bin/gunicorn --worker-class eventlet -w 1 --bind 0.0.0.0:5000 app:app

[Install]
WantedBy=multi-user.target
```

Start service:
```bash
sudo systemctl daemon-reload
sudo systemctl start poker
sudo systemctl enable poker
```

## Deploy to DigitalOcean

Similar to AWS EC2 - create a Droplet and follow the same steps.

## Using Docker

Create `Dockerfile`:
```dockerfile
FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000

CMD ["gunicorn", "--worker-class", "eventlet", "-w", "1", "--bind", "0.0.0.0:5000", "app:app"]
```

Build and run:
```bash
docker build -t poker-app .
docker run -p 5000:5000 -e SECRET_KEY=your-secret poker-app
```

## Troubleshooting

### Memory Issues
- TensorFlow models are large - ensure at least 1GB RAM
- Consider using lighter models or disabling AI for deployment

### WebSocket Issues
- Ensure your hosting platform supports WebSockets
- Check firewall/security group settings

### Model Loading Errors
- Verify models directory is included in deployment
- Check file permissions

### Performance
- Use CDN for static files
- Enable gzip compression
- Consider Redis for session management

## Custom Domain

After deployment, configure your domain:
1. Add A record pointing to your server IP
2. Configure SSL with Let's Encrypt:
```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

## Monitoring

Add application monitoring:
- Heroku: Use built-in metrics or add-ons
- AWS: CloudWatch
- Self-hosted: Install monitoring tools like Prometheus/Grafana
