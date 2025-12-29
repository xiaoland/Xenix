PRAGMA foreign_keys=OFF;--> statement-breakpoint
CREATE TABLE `__new_work_items` (
	`id` integer PRIMARY KEY AUTOINCREMENT NOT NULL,
	`work_item_id` text NOT NULL,
	`name` text NOT NULL,
	`description` text,
	`project_id` text NOT NULL,
	`task_ids` text,
	`status` text DEFAULT 'active' NOT NULL,
	`created_at` integer NOT NULL,
	`updated_at` integer NOT NULL
);
--> statement-breakpoint
INSERT INTO `__new_work_items`("id", "work_item_id", "name", "description", "project_id", "task_ids", "status", "created_at", "updated_at") SELECT "id", "work_item_id", "name", "description", "project_id", "task_ids", "status", "created_at", "updated_at" FROM `work_items`;--> statement-breakpoint
DROP TABLE `work_items`;--> statement-breakpoint
ALTER TABLE `__new_work_items` RENAME TO `work_items`;--> statement-breakpoint
PRAGMA foreign_keys=ON;--> statement-breakpoint
CREATE UNIQUE INDEX `work_items_work_item_id_unique` ON `work_items` (`work_item_id`);