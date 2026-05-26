"use client";

import { useState } from "react";
import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import {
  Settings,
  Globe,
  Mail,
  Shield,
  Database,
  HardDrive,
  ChevronLeft,
  RefreshCw,
  Info,
  Lock,
} from "lucide-react";

interface PlatformSettings {
  // General
  app_name: string;
  app_version: string;
  environment: string;

  // Storage
  storage_mode: string;
  s3_bucket_name: string;
  aws_region: string;

  // Processing
  pdf_dpi: number;
  max_file_size: number;
  pdf_max_pages: number;

  // Defaults
  default_currency: string;
  default_country: string;
  default_language: string;

  // Validation
  auto_approval_threshold: number;
  confidence_high: number;
  confidence_medium: number;

  // Rate Limiting
  rate_limit_enabled: boolean;
  rate_limit_requests: number;
  rate_limit_window: number;

  // Email
  smtp_enabled: boolean;
  smtp_host: string;
  smtp_port: number;
}

// Default settings (read-only display)
// In a real implementation, this would come from a backend API
const defaultSettings: PlatformSettings = {
  app_name: "Leaflet Extraction Platform",
  app_version: "1.0.0",
  environment: "development",
  storage_mode: "s3",
  s3_bucket_name: "leaflet-extraction-storage",
  aws_region: "us-east-1",
  pdf_dpi: 300,
  max_file_size: 104857600,
  pdf_max_pages: 100,
  default_currency: "EUR",
  default_country: "SI",
  default_language: "auto",
  auto_approval_threshold: 0.90,
  confidence_high: 0.90,
  confidence_medium: 0.75,
  rate_limit_enabled: true,
  rate_limit_requests: 100,
  rate_limit_window: 60,
  smtp_enabled: true,
  smtp_host: "smtp.gmail.com",
  smtp_port: 587,
};

export default function PlatformSettingsPage() {
  const [settings] = useState<PlatformSettings>(defaultSettings);
  const loading = false;

  const formatBytes = (bytes: number) => {
    const mb = bytes / (1024 * 1024);
    return `${mb.toFixed(0)} MB`;
  };

  return (
    <div className="container mx-auto pb-6 max-w-4xl bg-gray-50">
      {/* Header */}
      <div className="mb-8">
        <Link href="/admin">
          <Button variant="ghost" size="sm" className="mb-4 text-gray-600">
            <ChevronLeft className="h-4 w-4 mr-1" strokeWidth={1.5} />
            Back to Admin
          </Button>
        </Link>
        <div className="flex justify-between items-start">
          <div>
            <h1 className="text-2xl font-semibold mb-1 tracking-tight text-gray-900">
              Platform <span className="font-normal">Settings</span>
            </h1>
            <p className="text-sm text-gray-500">
              View platform configuration (read-only, configured via environment variables)
            </p>
          </div>
          <Badge variant="outline" className="bg-blue-50 text-blue-700 border-blue-200">
            <Lock className="h-3 w-3 mr-1" strokeWidth={1.5} />
            Read Only
          </Badge>
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-20">
          <RefreshCw className="h-8 w-8 animate-spin text-blue-600" />
          <span className="ml-3 text-gray-500">Loading settings...</span>
        </div>
      ) : settings ? (
        <div className="space-y-6">
          {/* Info Banner */}
          <Card className="bg-blue-50 border-blue-200">
            <CardContent className="p-4 flex items-start gap-3">
              <Info className="h-5 w-5 text-blue-600 mt-0.5" strokeWidth={1.5} />
              <div>
                <p className="text-sm text-blue-800 font-medium">Configuration via Environment Variables</p>
                <p className="text-sm text-blue-700 mt-1">
                  Platform settings are configured through environment variables in the <code className="bg-blue-100 px-1 rounded">.env</code> file
                  or Docker Compose configuration. Changes require a service restart.
                </p>
              </div>
            </CardContent>
          </Card>

          {/* General Settings */}
          <Card className="bg-white border-gray-200">
            <CardHeader className="border-b border-gray-200 bg-gray-50">
              <div className="flex items-center gap-3">
                <Settings className="h-5 w-5 text-blue-600" strokeWidth={1.5} />
                <div>
                  <CardTitle className="text-lg font-medium">General Settings</CardTitle>
                  <CardDescription>Application identity and environment</CardDescription>
                </div>
              </div>
            </CardHeader>
            <CardContent className="p-6 space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                  <Label className="text-gray-500 text-xs">Application Name</Label>
                  <p className="font-medium text-gray-900">{settings.app_name}</p>
                </div>
                <div>
                  <Label className="text-gray-500 text-xs">Version</Label>
                  <p className="font-medium text-gray-900">{settings.app_version}</p>
                </div>
                <div>
                  <Label className="text-gray-500 text-xs">Environment</Label>
                  <Badge variant="outline" className={
                    settings.environment === "production"
                      ? "bg-green-50 text-green-700 border-green-200"
                      : "bg-yellow-50 text-yellow-700 border-yellow-200"
                  }>
                    {settings.environment}
                  </Badge>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Storage Settings */}
          <Card className="bg-white border-gray-200">
            <CardHeader className="border-b border-gray-200 bg-gray-50">
              <div className="flex items-center gap-3">
                <HardDrive className="h-5 w-5 text-green-600" strokeWidth={1.5} />
                <div>
                  <CardTitle className="text-lg font-medium">Storage Configuration</CardTitle>
                  <CardDescription>File storage backend settings</CardDescription>
                </div>
              </div>
            </CardHeader>
            <CardContent className="p-6 space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                  <Label className="text-gray-500 text-xs">Storage Mode</Label>
                  <p className="font-medium text-gray-900 uppercase">{settings.storage_mode}</p>
                </div>
                <div>
                  <Label className="text-gray-500 text-xs">S3 Bucket</Label>
                  <p className="font-medium text-gray-900">{settings.s3_bucket_name}</p>
                </div>
                <div>
                  <Label className="text-gray-500 text-xs">AWS Region</Label>
                  <p className="font-medium text-gray-900">{settings.aws_region}</p>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Processing Settings */}
          <Card className="bg-white border-gray-200">
            <CardHeader className="border-b border-gray-200 bg-gray-50">
              <div className="flex items-center gap-3">
                <Database className="h-5 w-5 text-purple-600" strokeWidth={1.5} />
                <div>
                  <CardTitle className="text-lg font-medium">Processing Settings</CardTitle>
                  <CardDescription>PDF processing and file limits</CardDescription>
                </div>
              </div>
            </CardHeader>
            <CardContent className="p-6 space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                  <Label className="text-gray-500 text-xs">PDF DPI</Label>
                  <p className="font-medium text-gray-900">{settings.pdf_dpi}</p>
                </div>
                <div>
                  <Label className="text-gray-500 text-xs">Max File Size</Label>
                  <p className="font-medium text-gray-900">{formatBytes(settings.max_file_size)}</p>
                </div>
                <div>
                  <Label className="text-gray-500 text-xs">Max Pages per PDF</Label>
                  <p className="font-medium text-gray-900">{settings.pdf_max_pages}</p>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Default Region Settings */}
          <Card className="bg-white border-gray-200">
            <CardHeader className="border-b border-gray-200 bg-gray-50">
              <div className="flex items-center gap-3">
                <Globe className="h-5 w-5 text-blue-600" strokeWidth={1.5} />
                <div>
                  <CardTitle className="text-lg font-medium">Regional Defaults</CardTitle>
                  <CardDescription>Default currency, country, and language</CardDescription>
                </div>
              </div>
            </CardHeader>
            <CardContent className="p-6 space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                  <Label className="text-gray-500 text-xs">Default Currency</Label>
                  <p className="font-medium text-gray-900">{settings.default_currency}</p>
                </div>
                <div>
                  <Label className="text-gray-500 text-xs">Default Country</Label>
                  <p className="font-medium text-gray-900">{settings.default_country}</p>
                </div>
                <div>
                  <Label className="text-gray-500 text-xs">Default Language</Label>
                  <p className="font-medium text-gray-900">{settings.default_language}</p>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Validation Settings */}
          <Card className="bg-white border-gray-200">
            <CardHeader className="border-b border-gray-200 bg-gray-50">
              <div className="flex items-center gap-3">
                <Shield className="h-5 w-5 text-orange-600" strokeWidth={1.5} />
                <div>
                  <CardTitle className="text-lg font-medium">Validation Thresholds</CardTitle>
                  <CardDescription>Auto-approval and confidence settings</CardDescription>
                </div>
              </div>
            </CardHeader>
            <CardContent className="p-6 space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                  <Label className="text-gray-500 text-xs">Auto-Approval Threshold</Label>
                  <p className="font-medium text-gray-900">{(settings.auto_approval_threshold * 100).toFixed(0)}%</p>
                </div>
                <div>
                  <Label className="text-gray-500 text-xs">High Confidence</Label>
                  <p className="font-medium text-gray-900">{(settings.confidence_high * 100).toFixed(0)}%</p>
                </div>
                <div>
                  <Label className="text-gray-500 text-xs">Medium Confidence</Label>
                  <p className="font-medium text-gray-900">{(settings.confidence_medium * 100).toFixed(0)}%</p>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Rate Limiting */}
          <Card className="bg-white border-gray-200">
            <CardHeader className="border-b border-gray-200 bg-gray-50">
              <div className="flex items-center gap-3">
                <Shield className="h-5 w-5 text-red-600" strokeWidth={1.5} />
                <div>
                  <CardTitle className="text-lg font-medium">Rate Limiting</CardTitle>
                  <CardDescription>API rate limit configuration</CardDescription>
                </div>
              </div>
            </CardHeader>
            <CardContent className="p-6 space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                  <Label className="text-gray-500 text-xs">Rate Limiting</Label>
                  <Badge variant="outline" className={
                    settings.rate_limit_enabled
                      ? "bg-green-50 text-green-700 border-green-200"
                      : "bg-gray-100 text-gray-600"
                  }>
                    {settings.rate_limit_enabled ? "Enabled" : "Disabled"}
                  </Badge>
                </div>
                <div>
                  <Label className="text-gray-500 text-xs">Max Requests</Label>
                  <p className="font-medium text-gray-900">{settings.rate_limit_requests} requests</p>
                </div>
                <div>
                  <Label className="text-gray-500 text-xs">Time Window</Label>
                  <p className="font-medium text-gray-900">{settings.rate_limit_window} seconds</p>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Email Settings */}
          <Card className="bg-white border-gray-200">
            <CardHeader className="border-b border-gray-200 bg-gray-50">
              <div className="flex items-center gap-3">
                <Mail className="h-5 w-5 text-blue-600" strokeWidth={1.5} />
                <div>
                  <CardTitle className="text-lg font-medium">Email Configuration</CardTitle>
                  <CardDescription>SMTP settings for email notifications</CardDescription>
                </div>
              </div>
            </CardHeader>
            <CardContent className="p-6 space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                  <Label className="text-gray-500 text-xs">Email Sending</Label>
                  <Badge variant="outline" className={
                    settings.smtp_enabled
                      ? "bg-green-50 text-green-700 border-green-200"
                      : "bg-gray-100 text-gray-600"
                  }>
                    {settings.smtp_enabled ? "Enabled" : "Disabled"}
                  </Badge>
                </div>
                <div>
                  <Label className="text-gray-500 text-xs">SMTP Host</Label>
                  <p className="font-medium text-gray-900">{settings.smtp_host}</p>
                </div>
                <div>
                  <Label className="text-gray-500 text-xs">SMTP Port</Label>
                  <p className="font-medium text-gray-900">{settings.smtp_port}</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      ) : (
        <Card className="bg-white border-gray-200">
          <CardContent className="p-12 text-center">
            <Settings className="h-12 w-12 mx-auto mb-4 text-gray-400" strokeWidth={1.5} />
            <h3 className="text-lg font-medium text-gray-900 mb-2">Failed to Load Settings</h3>
            <p className="text-gray-500">Unable to retrieve platform settings.</p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
