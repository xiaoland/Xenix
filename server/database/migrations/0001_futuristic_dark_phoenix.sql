ALTER TABLE `model_results` ADD `parent_task_id` text;--> statement-breakpoint
ALTER TABLE `model_results` ADD `training_type` text DEFAULT 'auto';