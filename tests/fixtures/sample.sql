{{
    config(
        materialized='table',
        schema='marts',
        tags=['canonical', 'scoring']
    )
}}

/*
    Sample dbt model for graphify test fixtures.
    Tests ref(), source(), config(), and dynamic ref detection.
*/

with upstream_model as (
    select *
    from {{ ref('stg_orders') }}
),

raw_data as (
    select *
    from {{ source('raw_schema', 'orders_table') }}
),

another_ref as (
    select *
    from {{ ref('dim_customers') }}
),

secondary_source as (
    select *
    from {{ source('external', 'payments') }}
)

select
    u.order_id,
    u.customer_id,
    c.customer_name,
    r.raw_amount,
    s.payment_status
from upstream_model as u
inner join another_ref as c on u.customer_id = c.customer_id
left join raw_data as r on u.order_id = r.order_id
left join secondary_source as s on u.order_id = s.order_id
