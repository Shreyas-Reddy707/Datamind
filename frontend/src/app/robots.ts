import { MetadataRoute } from "next";

export default function robots(): MetadataRoute.Robots {
  const baseUrl = process.env.NEXT_PUBLIC_SITE_URL || "https://datamind.ai";

  return {
    rules: [
      {
        userAgent: "*",
        allow: "/",
        disallow: [
          "/workspace/",
          "/api/",
          "/dashboard",
          "/dashboard/",
          "/account",
          "/account/",
          "/settings",
          "/settings/",
        ],
      },
    ],
    sitemap: `${baseUrl}/sitemap.xml`,
  };
}

