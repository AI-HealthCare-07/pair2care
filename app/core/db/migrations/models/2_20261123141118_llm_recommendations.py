from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS `recommendations` (
    `id` BIGINT NOT NULL PRIMARY KEY AUTO_INCREMENT,
    `rec_type` VARCHAR(16) NOT NULL COMMENT 'DAILY_ACTION: DAILY_ACTION\nMEAL_ALTERNATIVE: MEAL_ALTERNATIVE\nWEATHER_TIP: WEATHER_TIP\nRISK_EXPLANATION: RISK_EXPLANATION\nWEEKLY_REPORT: WEEKLY_REPORT',
    `target_on` DATE NOT NULL,
    `status` VARCHAR(10) NOT NULL COMMENT 'PENDING: PENDING\nPROCESSING: PROCESSING\nCOMPLETED: COMPLETED\nFAILED: FAILED' DEFAULT 'PENDING',
    `task_id` CHAR(36),
    `content` LONGTEXT,
    `sources` JSON,
    `risk_prediction_id` BIGINT UNIQUE,
    `meal_id` BIGINT UNIQUE,
    `model` VARCHAR(50),
    `prompt_version` VARCHAR(30),
    `retry_count` INT NOT NULL DEFAULT 0,
    `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    `updated_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6) ON UPDATE CURRENT_TIMESTAMP(6),
    `user_id` BIGINT NOT NULL,
    CONSTRAINT `fk_recommen_users_c1b33b7a` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE,
    KEY `idx_recommendat_user_id_d2f3da` (`user_id`, `rec_type`, `target_on`)
) CHARACTER SET utf8mb4;
        CREATE TABLE IF NOT EXISTS `llm_usage_logs` (
    `id` BIGINT NOT NULL PRIMARY KEY AUTO_INCREMENT,
    `meal_id` BIGINT,
    `feature` VARCHAR(16) NOT NULL COMMENT 'DAILY_ACTION: DAILY_ACTION\nMEAL_ALTERNATIVE: MEAL_ALTERNATIVE\nWEATHER_TIP: WEATHER_TIP\nRISK_EXPLANATION: RISK_EXPLANATION\nWEEKLY_REPORT: WEEKLY_REPORT\nMEAL_VISION: MEAL_VISION\nRAG_EMBEDDING: RAG_EMBEDDING',
    `model` VARCHAR(50) NOT NULL,
    `input_tokens` INT NOT NULL DEFAULT 0,
    `output_tokens` INT NOT NULL DEFAULT 0,
    `cache_creation_tokens` INT NOT NULL DEFAULT 0,
    `cache_read_tokens` INT NOT NULL DEFAULT 0,
    `estimated_cost_usd` DECIMAL(10,6),
    `is_success` BOOL NOT NULL DEFAULT 1,
    `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    `recommendation_id` BIGINT,
    `user_id` BIGINT,
    CONSTRAINT `fk_llm_usag_recommen_00b39247` FOREIGN KEY (`recommendation_id`) REFERENCES `recommendations` (`id`) ON DELETE SET NULL,
    CONSTRAINT `fk_llm_usag_users_1d678f84` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE SET NULL,
    KEY `idx_llm_usage_l_feature_163b9b` (`feature`, `created_at`),
    KEY `idx_llm_usage_l_user_id_78ebfb` (`user_id`, `created_at`)
) CHARACTER SET utf8mb4;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        DROP TABLE IF EXISTS `llm_usage_logs`;
        DROP TABLE IF EXISTS `recommendations`;"""


MODELS_STATE = (
    "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"
)
