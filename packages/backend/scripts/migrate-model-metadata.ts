/**
 * Migration script to populate model_metadata table from model_metadata.json
 *
 * Usage: pnpm run migrate:models
 */

import fs from "fs/promises";
import path from "path";
import { fileURLToPath } from "url";
import { db } from "../src/database/index.js";
import { modelMetadata } from "../src/database/schema.js";
import { eq } from "drizzle-orm";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

interface ModelMetadata {
  name: string;
  display_name: string;
  type: string;
  description: string;
  param_schema: Record<string, any>;
  param_grid_schema: Record<string, any>;
  default_params: Record<string, any>;
  default_param_grid: Record<string, any>;
  available: boolean;
}

async function migrateModelMetadata() {
  console.log("🚀 Starting model metadata migration...\n");

  try {
    // Read the model metadata JSON file
    const metadataPath = path.join(
      __dirname,
      "..",
      "..",
      "ml-backend",
      "model_metadata.json",
    );

    console.log(`📖 Reading metadata from: ${metadataPath}`);
    const fileContent = await fs.readFile(metadataPath, "utf-8");
    const models: ModelMetadata[] = JSON.parse(fileContent);

    console.log(`📋 Found ${models.length} models to process\n`);

    let insertedCount = 0;
    let updatedCount = 0;
    let skippedCount = 0;

    // Process each model
    for (const model of models) {
      try {
        console.log(`Processing: ${model.name}...`);

        // Check if model already exists
        const [existing] = await db
          .select()
          .from(modelMetadata)
          .where(eq(modelMetadata.name, model.name))
          .limit(1);

        if (existing) {
          // Update existing model
          await db
            .update(modelMetadata)
            .set({
              category: model.type,
              label: model.display_name,
              paramSchema: model.param_schema,
              paramGridSchema: model.param_grid_schema,
              updatedAt: new Date(),
            })
            .where(eq(modelMetadata.name, model.name));

          console.log(`  ✅ Updated: ${model.name}`);
          updatedCount++;
        } else {
          // Insert new model
          await db.insert(modelMetadata).values({
            category: model.type,
            name: model.name,
            label: model.display_name,
            paramSchema: model.param_schema,
            paramGridSchema: model.param_grid_schema,
          });

          console.log(`  ✨ Inserted: ${model.name}`);
          insertedCount++;
        }
      } catch (error: any) {
        console.error(`  ❌ Failed to process ${model.name}:`, error.message);
        skippedCount++;
      }
    }

    // Summary
    console.log("\n" + "=".repeat(60));
    console.log("✅ Migration completed!");
    console.log("=".repeat(60));
    console.log(`📊 Summary:`);
    console.log(`  - Total models: ${models.length}`);
    console.log(`  - Inserted: ${insertedCount}`);
    console.log(`  - Updated: ${updatedCount}`);
    console.log(`  - Skipped/Failed: ${skippedCount}`);
    console.log("=".repeat(60) + "\n");

    process.exit(0);
  } catch (error: any) {
    console.error("\n❌ Migration failed:", error.message);
    console.error(error);
    process.exit(1);
  }
}

// Run the migration
migrateModelMetadata();
