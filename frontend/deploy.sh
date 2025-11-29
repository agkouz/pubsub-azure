#!/bin/bash

# Azure App Service deployment script for React

# Install dependencies
echo "Installing dependencies..."
npm install

# Build the React app with production environment variables
echo "Building React app..."
npm run build

echo "Deployment complete!"
